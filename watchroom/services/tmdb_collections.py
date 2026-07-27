from dataclasses import dataclass

from django.db.models import Max
from django.utils import timezone

from watchroom.models import (
    Franchise,
    FranchiseMembership,
    MediaWork,
)


class TMDBCollectionSyncError(
    Exception
):
    """Raised when collection sync fails."""


@dataclass(frozen=True)
class TMDBCollectionSyncResult:
    franchise: Franchise
    membership: FranchiseMembership
    franchise_created: bool
    membership_created: bool


def _collection_position(
    *,
    work,
    collection_details,
    franchise,
):
    for position, part in enumerate(
        collection_details.get(
            "parts",
            [],
        ),
        start=1,
    ):
        if (
            part.get("tmdb_id")
            == work.tmdb_id
        ):
            return position

    maximum = (
        FranchiseMembership.objects
        .filter(
            franchise=franchise,
        )
        .aggregate(
            maximum=Max("position")
        )
        .get("maximum")
    )

    return (maximum or 0) + 1


def _update_franchise_metadata(
    *,
    franchise,
    collection_details,
):
    name = str(
        collection_details.get("name")
        or ""
    ).strip()

    if name:
        franchise.name = name

    overview = str(
        collection_details.get(
            "overview"
        )
        or ""
    ).strip()

    if overview:
        franchise.overview = overview

    poster_url = str(
        collection_details.get(
            "poster_url"
        )
        or ""
    ).strip()

    if poster_url:
        franchise.poster_url = (
            poster_url
        )

    backdrop_url = str(
        collection_details.get(
            "backdrop_url"
        )
        or ""
    ).strip()

    if backdrop_url:
        franchise.backdrop_url = (
            backdrop_url
        )

    payload = collection_details.get(
        "tmdb_payload"
    )

    if isinstance(payload, dict):
        franchise.tmdb_payload = payload

    franchise.tmdb_synced_at = (
        timezone.now()
    )

    franchise.full_clean()
    franchise.save(
        update_fields=[
            "name",
            "overview",
            "poster_url",
            "backdrop_url",
            "tmdb_payload",
            "tmdb_synced_at",
            "updated_at",
        ]
    )


def sync_tmdb_movie_collection(
    *,
    work,
    collection_details,
):
    if not collection_details:
        return None

    if (
        work.media_type
        != MediaWork.MediaType.MOVIE
    ):
        raise TMDBCollectionSyncError(
            (
                "Only movies can be linked "
                "through TMDB Collections."
            )
        )

    try:
        collection_id = int(
            collection_details.get(
                "tmdb_collection_id"
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise TMDBCollectionSyncError(
            (
                "TMDB collection identity "
                "is invalid."
            )
        ) from error

    if collection_id <= 0:
        raise TMDBCollectionSyncError(
            (
                "TMDB collection identity "
                "must be positive."
            )
        )

    franchise, franchise_created = (
        Franchise.objects.get_or_create(
            tmdb_collection_id=(
                collection_id
            ),
            defaults={
                "name": (
                    collection_details.get(
                        "name"
                    )
                    or (
                        "TMDB Collection "
                        f"{collection_id}"
                    )
                ),
            },
        )
    )

    _update_franchise_metadata(
        franchise=franchise,
        collection_details=(
            collection_details
        ),
    )

    position = _collection_position(
        work=work,
        collection_details=(
            collection_details
        ),
        franchise=franchise,
    )

    membership, membership_created = (
        FranchiseMembership.objects
        .get_or_create(
            franchise=franchise,
            media_work=work,
            defaults={
                "position": position,
                "role": (
                    FranchiseMembership
                    .Role.MAIN
                ),
            },
        )
    )

    return TMDBCollectionSyncResult(
        franchise=franchise,
        membership=membership,
        franchise_created=(
            franchise_created
        ),
        membership_created=(
            membership_created
        ),
    )


