from django.core.exceptions import (
    ValidationError,
)
from django.db import (
    IntegrityError,
    transaction,
)
from django.utils import timezone

from watchroom.models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)
from watchroom.services.tmdb_client import (
    TMDBClient,
    TMDBNotFoundError,
)
from watchroom.services.tmdb_normalizer import (
    TMDBNormalizationError,
    normalize_collection_details,
    normalize_movie_details,
    normalize_series_details,
)
from watchroom.services.tmdb_collections import (
    TMDBCollectionSyncError,
    sync_tmdb_movie_collection,
)

VALID_IMPORT_STATUSES = {
    WatchEntry.Status.PLAN_TO_WATCH,
    WatchEntry.Status.COMPLETED,
    WatchEntry.Status.DROPPED,
}


class TMDBImportError(Exception):
    """Base exception for TMDB imports."""


class TMDBDuplicateWorkError(
    TMDBImportError
):
    def __init__(
        self,
        existing_work,
    ):
        self.existing_work = existing_work

        super().__init__(
            (
                f"{existing_work.title} "
                "is already in the library."
            )
        )


def validate_tmdb_media_type(
    media_type,
):
    if media_type not in {
        MediaWork.MediaType.MOVIE,
        MediaWork.MediaType.SERIES,
    }:
        raise TMDBImportError(
            "Unsupported TMDB media type."
        )

    return media_type


def fetch_tmdb_details(
    *,
    media_type,
    tmdb_id,
    client=None,
):
    media_type = (
        validate_tmdb_media_type(
            media_type
        )
    )
    client = client or TMDBClient()

    try:
        if (
            media_type
            == MediaWork.MediaType.MOVIE
        ):
            payload = client.get_movie(
                tmdb_id
            )

            details = (
                normalize_movie_details(
                    payload
                )
            )

            collection_stub = payload.get(
                "belongs_to_collection"
            )

            if isinstance(
                collection_stub,
                dict,
            ):
                collection_id = (
                    collection_stub.get("id")
                )

                if collection_id:
                    try:
                        collection_payload = (
                            client.get_collection(
                                collection_id
                            )
                        )
                    except TMDBNotFoundError:
                        collection_payload = None

                    if collection_payload:
                        try:
                            details[
                                "collection"
                            ] = (
                                normalize_collection_details(
                                    collection_payload
                                )
                            )
                        except (
                            TMDBNormalizationError
                        ):
                            details[
                                "collection"
                            ] = None

            return details

        payload = client.get_series(
            tmdb_id
        )

        return normalize_series_details(
            payload
        )

    except TMDBNormalizationError as error:
        raise TMDBImportError(
            (
                "TMDB returned details that "
                "could not be normalized."
            )
        ) from error


def _validate_import_status(status):
    if status not in VALID_IMPORT_STATUSES:
        raise TMDBImportError(
            (
                "The selected initial status "
                "cannot be used during import."
            )
        )

    return status


def _validate_presentation(
    presentation,
):
    valid_presentations = {
        value
        for value, _label
        in MediaWork.Presentation.choices
    }

    if presentation not in valid_presentations:
        raise TMDBImportError(
            "Invalid presentation type."
        )

    return presentation


def _existing_work(
    *,
    media_type,
    tmdb_id,
):
    return (
        MediaWork.objects.filter(
            media_type=media_type,
            tmdb_id=tmdb_id,
        )
        .first()
    )


def _create_historical_run(
    *,
    entry,
):
    status_map = {
        WatchEntry.Status.COMPLETED: (
            ViewingRun.Status.COMPLETED
        ),
        WatchEntry.Status.DROPPED: (
            ViewingRun.Status.DROPPED
        ),
    }

    run_status = status_map.get(
        entry.status
    )

    if run_status is None:
        return None

    progress_minutes = None

    if (
        run_status
        == ViewingRun.Status.COMPLETED
        and entry.media_work.media_type
        == MediaWork.MediaType.MOVIE
    ):
        progress_minutes = (
            entry.media_work.runtime_minutes
        )

    return ViewingRun.objects.create(
        watch_entry=entry,
        number=1,
        status=run_status,
        progress_minutes=progress_minutes,
    )


def _create_series_seasons(
    *,
    work,
    season_details,
):
    created_seasons = []
    seen_numbers = set()

    for season_data in (
        season_details or []
    ):
        season_number = season_data.get(
            "season_number"
        )

        if season_number in seen_numbers:
            continue

        seen_numbers.add(
            season_number
        )

        season = Season(
            media_work=work,
            tmdb_id=season_data.get(
                "tmdb_id"
            ),
            season_number=season_number,
            name=season_data.get(
                "name",
                "",
            ),
            episode_count=season_data.get(
                "episode_count",
                0,
            ),
            air_date=season_data.get(
                "air_date"
            ),
            poster_url=season_data.get(
                "poster_url",
                "",
            ),
            tmdb_payload=season_data.get(
                "tmdb_payload",
                {},
            ),
        )

        season.full_clean()
        season.save()

        created_seasons.append(
            season
        )

    return created_seasons


def _create_completed_series_progress(
    *,
    viewing_run,
    seasons,
):
    regular_seasons = [
        season
        for season in seasons
        if (
            season.season_number > 0
            and season.episode_count > 0
        )
    ]

    if not regular_seasons:
        raise TMDBImportError(
            (
                "A completed series requires "
                "at least one known regular "
                "season with episodes."
            )
        )

    for season in regular_seasons:
        SeasonProgress.objects.create(
            viewing_run=viewing_run,
            season=season,
            episodes_watched=(
                season.episode_count
            ),
        )


def import_tmdb_work(
    *,
    details,
    status,
    notes="",
    presentation=None,
):
    if not isinstance(details, dict):
        raise TMDBImportError(
            "TMDB details are invalid."
        )

    media_type = (
        validate_tmdb_media_type(
            details.get("media_type")
        )
    )
    status = _validate_import_status(
        status
    )

    tmdb_id = details.get(
        "tmdb_id"
    )

    if not tmdb_id:
        raise TMDBImportError(
            "TMDB details do not contain an ID."
        )

    presentation = (
        presentation
        or details.get("presentation")
    )
    presentation = (
        _validate_presentation(
            presentation
        )
    )

    existing = _existing_work(
        media_type=media_type,
        tmdb_id=tmdb_id,
    )

    if existing is not None:
        raise TMDBDuplicateWorkError(
            existing
        )

    try:
        with transaction.atomic():
            work = MediaWork(
                tmdb_id=tmdb_id,
                media_type=media_type,
                title=details.get(
                    "title",
                    "",
                ),
                original_title=details.get(
                    "original_title",
                    "",
                ),
                overview=details.get(
                    "overview",
                    "",
                ),
                presentation=presentation,
                original_language=details.get(
                    "original_language",
                    "",
                ),
                first_release_date=details.get(
                    "first_release_date"
                ),
                runtime_minutes=details.get(
                    "runtime_minutes"
                ),
                external_status=details.get(
                    "external_status",
                    "",
                ),
                poster_url=details.get(
                    "poster_url",
                    "",
                ),
                backdrop_url=details.get(
                    "backdrop_url",
                    "",
                ),
                genres=details.get(
                    "genres",
                    [],
                ),
                origin_countries=details.get(
                    "origin_countries",
                    [],
                ),
                networks=details.get(
                    "networks",
                    [],
                ),
                tmdb_payload=details.get(
                    "tmdb_payload",
                    {},
                ),
                tmdb_synced_at=timezone.now(),
            )

            work.full_clean()
            work.save()

            if (
                media_type
                == MediaWork.MediaType.MOVIE
            ):
                sync_tmdb_movie_collection(
                    work=work,
                    collection_details=(
                        details.get("collection")
                    ),
                )

            entry = WatchEntry.objects.create(
                media_work=work,
                status=status,
                notes=notes,
            )

            created_seasons = []

            if (
                media_type
                == MediaWork.MediaType.SERIES
            ):
                created_seasons = (
                    _create_series_seasons(
                        work=work,
                        season_details=(
                            details.get(
                                "seasons",
                                [],
                            )
                        ),
                    )
                )

            historical_run = (
                _create_historical_run(
                    entry=entry
                )
            )

            if (
                historical_run is not None
                and historical_run.status
                == ViewingRun.Status.COMPLETED
                and media_type
                == MediaWork.MediaType.SERIES
            ):
                _create_completed_series_progress(
                    viewing_run=(
                        historical_run
                    ),
                    seasons=created_seasons,
                )

            return work

    except IntegrityError as error:
        existing = _existing_work(
            media_type=media_type,
            tmdb_id=tmdb_id,
        )

        if existing is not None:
            raise TMDBDuplicateWorkError(
                existing
            ) from error

        raise TMDBImportError(
            (
                "The TMDB work could not be "
                "saved because of a database "
                "constraint."
            )
        ) from error

    except TMDBCollectionSyncError as error:
        raise TMDBImportError(
            (
                "The movie was not imported "
                "because its TMDB collection "
                "could not be synchronized."
            )
        ) from error

    except ValidationError as error:
        raise TMDBImportError(
            "The TMDB work failed local validation."
        ) from error


