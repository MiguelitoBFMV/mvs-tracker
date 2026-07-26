from dataclasses import dataclass

from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from watchroom.models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
)
from watchroom.services.tmdb_importer import (
    fetch_tmdb_details,
)


class TMDBRefreshError(Exception):
    """Raised when a local TMDB refresh fails."""


@dataclass(frozen=True)
class TMDBRefreshResult:
    work: MediaWork
    created_seasons: int = 0
    updated_seasons: int = 0
    preserved_episode_totals: int = 0
    preserved_runtime: bool = False


WORK_METADATA_FIELDS = (
    "title",
    "original_title",
    "overview",
    "original_language",
    "first_release_date",
    "external_status",
    "poster_url",
    "backdrop_url",
    "genres",
    "origin_countries",
    "networks",
)


def _has_usable_value(value):
    return value not in (
        None,
        "",
        [],
        {},
    )


def _positive_integer_or_none(value):
    try:
        value = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if value <= 0:
        return None

    return value


def _non_negative_integer(value):
    try:
        value = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(value, 0)


def _maximum_movie_progress(work):
    maximum = (
        ViewingRun.objects.filter(
            watch_entry__media_work=work,
        )
        .aggregate(
            maximum=Max(
                "progress_minutes"
            )
        )
        .get("maximum")
    )

    return maximum or 0


def _maximum_season_progress(season):
    maximum = (
        SeasonProgress.objects.filter(
            season=season,
        )
        .aggregate(
            maximum=Max(
                "episodes_watched"
            )
        )
        .get("maximum")
    )

    return maximum or 0


def _update_work_metadata(
    *,
    work,
    details,
):
    preserved_runtime = False

    for field_name in WORK_METADATA_FIELDS:
        incoming_value = details.get(
            field_name
        )

        if _has_usable_value(
            incoming_value
        ):
            setattr(
                work,
                field_name,
                incoming_value,
            )

    if (
        work.media_type
        == MediaWork.MediaType.MOVIE
    ):
        incoming_runtime = (
            _positive_integer_or_none(
                details.get(
                    "runtime_minutes"
                )
            )
        )

        if incoming_runtime is not None:
            maximum_progress = (
                _maximum_movie_progress(
                    work
                )
            )

            if (
                incoming_runtime
                >= maximum_progress
            ):
                work.runtime_minutes = (
                    incoming_runtime
                )
            else:
                preserved_runtime = True
    else:
        work.runtime_minutes = None

    incoming_payload = details.get(
        "tmdb_payload"
    )

    if isinstance(
        incoming_payload,
        dict,
    ):
        work.tmdb_payload = (
            incoming_payload
        )

    work.tmdb_synced_at = timezone.now()

    work.full_clean()
    work.save(
        update_fields=[
            *WORK_METADATA_FIELDS,
            "runtime_minutes",
            "tmdb_payload",
            "tmdb_synced_at",
            "updated_at",
        ]
    )

    return preserved_runtime


def _create_season(
    *,
    work,
    season_data,
):
    season = Season(
        media_work=work,
        tmdb_id=season_data.get(
            "tmdb_id"
        ),
        season_number=(
            _non_negative_integer(
                season_data.get(
                    "season_number"
                )
            )
        ),
        name=season_data.get(
            "name",
            "",
        ),
        episode_count=(
            _non_negative_integer(
                season_data.get(
                    "episode_count"
                )
            )
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

    return season


def _update_season(
    *,
    season,
    season_data,
):
    preserved_total = False

    incoming_tmdb_id = season_data.get(
        "tmdb_id"
    )

    if incoming_tmdb_id:
        season.tmdb_id = incoming_tmdb_id

    incoming_name = season_data.get(
        "name"
    )

    if incoming_name:
        season.name = incoming_name

    incoming_count = (
        _non_negative_integer(
            season_data.get(
                "episode_count"
            )
        )
    )

    if incoming_count > 0:
        maximum_progress = (
            _maximum_season_progress(
                season
            )
        )

        if incoming_count >= maximum_progress:
            season.episode_count = (
                incoming_count
            )
        else:
            preserved_total = True

    incoming_air_date = season_data.get(
        "air_date"
    )

    if incoming_air_date is not None:
        season.air_date = (
            incoming_air_date
        )

    incoming_poster = season_data.get(
        "poster_url"
    )

    if incoming_poster:
        season.poster_url = (
            incoming_poster
        )

    incoming_payload = season_data.get(
        "tmdb_payload"
    )

    if isinstance(
        incoming_payload,
        dict,
    ):
        season.tmdb_payload = (
            incoming_payload
        )

    season.full_clean()
    season.save(
        update_fields=[
            "tmdb_id",
            "name",
            "episode_count",
            "air_date",
            "poster_url",
            "tmdb_payload",
            "updated_at",
        ]
    )

    return preserved_total


def _sync_series_seasons(
    *,
    work,
    season_details,
):
    existing_by_number = {
        season.season_number: season
        for season in (
            Season.objects
            .select_for_update()
            .filter(
                media_work=work
            )
        )
    }

    seen_numbers = set()
    created_count = 0
    updated_count = 0
    preserved_count = 0

    for season_data in (
        season_details or []
    ):
        if not isinstance(
            season_data,
            dict,
        ):
            continue

        season_number = (
            _non_negative_integer(
                season_data.get(
                    "season_number"
                )
            )
        )

        if season_number in seen_numbers:
            continue

        seen_numbers.add(
            season_number
        )

        existing_season = (
            existing_by_number.get(
                season_number
            )
        )

        if existing_season is None:
            _create_season(
                work=work,
                season_data=season_data,
            )
            created_count += 1
            continue

        preserved_total = (
            _update_season(
                season=existing_season,
                season_data=season_data,
            )
        )

        updated_count += 1

        if preserved_total:
            preserved_count += 1

    return (
        created_count,
        updated_count,
        preserved_count,
    )


def _validate_refresh_identity(
    *,
    work,
    details,
):
    if not isinstance(details, dict):
        raise TMDBRefreshError(
            "TMDB refresh details are invalid."
        )

    if (
        details.get("media_type")
        != work.media_type
    ):
        raise TMDBRefreshError(
            (
                "TMDB returned a different "
                "media type."
            )
        )

    try:
        details_tmdb_id = int(
            details.get("tmdb_id")
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise TMDBRefreshError(
            (
                "TMDB returned an invalid "
                "external ID."
            )
        ) from error

    if details_tmdb_id != work.tmdb_id:
        raise TMDBRefreshError(
            (
                "TMDB returned a different "
                "external identity."
            )
        )


def refresh_work_from_tmdb(
    *,
    work,
    client=None,
):
    if work.tmdb_id is None:
        raise TMDBRefreshError(
            (
                "This work is not linked "
                "to TMDB."
            )
        )

    details = fetch_tmdb_details(
        media_type=work.media_type,
        tmdb_id=work.tmdb_id,
        client=client,
    )

    _validate_refresh_identity(
        work=work,
        details=details,
    )

    try:
        with transaction.atomic():
            locked_work = (
                MediaWork.objects
                .select_for_update()
                .get(pk=work.pk)
            )

            preserved_runtime = (
                _update_work_metadata(
                    work=locked_work,
                    details=details,
                )
            )

            created_seasons = 0
            updated_seasons = 0
            preserved_totals = 0

            if (
                locked_work.media_type
                == MediaWork.MediaType.SERIES
            ):
                (
                    created_seasons,
                    updated_seasons,
                    preserved_totals,
                ) = _sync_series_seasons(
                    work=locked_work,
                    season_details=(
                        details.get(
                            "seasons",
                            [],
                        )
                    ),
                )

            return TMDBRefreshResult(
                work=locked_work,
                created_seasons=(
                    created_seasons
                ),
                updated_seasons=(
                    updated_seasons
                ),
                preserved_episode_totals=(
                    preserved_totals
                ),
                preserved_runtime=(
                    preserved_runtime
                ),
            )

    except ValidationError as error:
        raise TMDBRefreshError(
            (
                "Refreshed TMDB metadata failed "
                "local validation."
            )
        ) from error


