import copy

from django.db import transaction
from django.utils import timezone

from mal_data.models import (
    MangaEntry,
    ManualTrackedManga,
)
from mal_data.services.anilist_client import (
    AniListClient,
)
from mal_data.services.mal_client import (
    MyAnimeListClient,
)
from mal_data.services.manga_list_sync import (
    SYNC_COMPARE_FIELDS,
    build_manga_defaults,
    create_manga_sync_events,
    manga_field_changed,
)


ANILIST_STATUS_MAP = {
    "RELEASING": "currently_publishing",
    "FINISHED": "finished",
    "HIATUS": "on_hiatus",
    "CANCELLED": "discontinued",
    "NOT_YET_RELEASED": "not_yet_published",
}


def anilist_date_to_iso(value):
    if not value:
        return None

    year = value.get("year")
    month = value.get("month")
    day = value.get("day")

    if not all((year, month, day)):
        return None

    return f"{year:04d}-{month:02d}-{day:02d}"


def resolve_anilist_media_type(media):
    media_format = media.get("format")
    country = media.get("countryOfOrigin")

    if media_format == "NOVEL":
        return "light_novel"

    if media_format == "ONE_SHOT":
        return "one_shot"

    if country == "KR":
        return "manhwa"

    if country == "CN":
        return "manhua"

    return "manga"


def build_node_from_anilist(
    media,
    tracked_entry,
):
    titles = media.get("title") or {}
    cover = media.get("coverImage") or {}

    return {
        "id": tracked_entry.mal_id,
        "title": (
            titles.get("romaji")
            or titles.get("english")
            or titles.get("native")
            or tracked_entry.title_snapshot
            or ""
        ),
        "alternative_titles": {
            "ja": titles.get("native"),
            "en": titles.get("english"),
        },
        "main_picture": {
            "large": (
                cover.get("extraLarge")
                or cover.get("large")
            ),
            "medium": cover.get("medium"),
        },
        "media_type": (
            resolve_anilist_media_type(media)
        ),
        "status": ANILIST_STATUS_MAP.get(
            media.get("status"),
            (
                media.get("status") or ""
            ).lower(),
        ),
        "num_volumes": (
            media.get("volumes") or 0
        ),
        "num_chapters": (
            media.get("chapters") or 0
        ),
        "start_date": anilist_date_to_iso(
            media.get("startDate")
        ),
        "end_date": anilist_date_to_iso(
            media.get("endDate")
        ),
    }


def build_manual_fallback(tracked_entry):
    return {
        "status": tracked_entry.status,
        "score": tracked_entry.score,
        "num_volumes_read": (
            tracked_entry.volumes_read
        ),
        "num_chapters_read": (
            tracked_entry.chapters_read
        ),
        "is_rereading": (
            tracked_entry.is_rereading
        ),
    }


def sync_manual_tracked_manga_entry(
    tracked_entry,
    *,
    mal_client=None,
    anilist_client=None,
):
    mal_client = (
        mal_client or MyAnimeListClient()
    )
    anilist_client = (
        anilist_client or AniListClient()
    )

    anilist_media = (
        anilist_client.fetch_manga_by_mal_id(
            tracked_entry.mal_id
        )
    )

    mal_details = None

    if anilist_media:
        node = build_node_from_anilist(
            anilist_media,
            tracked_entry,
        )
        metadata_source = "anilist"

    else:
        mal_details = (
            mal_client.fetch_manga_details(
                tracked_entry.mal_id
            )
        )

        if not mal_details:
            raise ValueError(
                "Ni AniList ni MAL devolvieron "
                "metadatos para el manga "
                f"{tracked_entry.mal_id}."
            )

        node = mal_details
        metadata_source = "mal"

    my_list_status = (
        mal_client.fetch_manga_my_list_status(
            tracked_entry.mal_id
        )
    )

    resolved_list_status = (
        my_list_status
        or build_manual_fallback(
            tracked_entry
        )
    )

    item = {
        "node": node,
        "list_status": resolved_list_status,
    }

    sync_time = timezone.now()

    mal_id, defaults = build_manga_defaults(
        item,
        sync_time=sync_time,
    )

    defaults["raw_data"] = {
        "source": (
            "manual_tracked_manga_sync"
        ),
        "metadata_source": metadata_source,
        "anilist": anilist_media,
        "mal_details": mal_details,
        "my_list_status": my_list_status,
        "manual_fallback": (
            build_manual_fallback(
                tracked_entry
            )
        ),
    }

    with transaction.atomic():
        manga = (
            MangaEntry.objects
            .filter(mal_id=mal_id)
            .first()
        )

        created = manga is None

        if created:
            manga = MangaEntry.objects.create(
                mal_id=mal_id,
                **defaults,
            )

            create_manga_sync_events(
                manga=manga,
                previous=None,
                created=True,
            )

        else:
            previous = copy.copy(manga)

            changed_fields = [
                field_name
                for field_name
                in SYNC_COMPARE_FIELDS
                if manga_field_changed(
                    field_name,
                    getattr(
                        manga,
                        field_name,
                    ),
                    defaults[field_name],
                )
            ]

            for field_name in changed_fields:
                setattr(
                    manga,
                    field_name,
                    defaults[field_name],
                )

            manga.raw_data = defaults[
                "raw_data"
            ]
            manga.last_synced_at = sync_time

            update_fields = list(
                dict.fromkeys(
                    [
                        *changed_fields,
                        "raw_data",
                        "last_synced_at",
                    ]
                )
            )

            manga.save(
                update_fields=update_fields
            )

            if changed_fields:
                create_manga_sync_events(
                    manga=manga,
                    previous=previous,
                    created=False,
                )

        tracker_values = {
            "title_snapshot": (
                manga.display_title
            ),
            "status": manga.list_status,
            "chapters_read": (
                manga.num_chapters_read
            ),
            "volumes_read": (
                manga.num_volumes_read
            ),
            "score": manga.score,
            "is_rereading": (
                manga.is_rereading
            ),
            "active": True,
        }

        tracker_changed_fields = []

        for field_name, new_value in (
            tracker_values.items()
        ):
            if (
                getattr(
                    tracked_entry,
                    field_name,
                )
                != new_value
            ):
                setattr(
                    tracked_entry,
                    field_name,
                    new_value,
                )
                tracker_changed_fields.append(
                    field_name
                )

        if tracker_changed_fields:
            tracked_entry.save(
                update_fields=[
                    *tracker_changed_fields,
                    "updated_at",
                ]
            )

    return manga, created


def sync_all_manual_tracked_manga():
    mal_client = MyAnimeListClient()
    anilist_client = AniListClient()

    tracked_entries = list(
        ManualTrackedManga.objects
        .filter(active=True)
        .order_by(
            "title_snapshot",
            "mal_id",
        )
    )

    results = []

    for tracked_entry in tracked_entries:
        try:
            manga, created = (
                sync_manual_tracked_manga_entry(
                    tracked_entry,
                    mal_client=mal_client,
                    anilist_client=(
                        anilist_client
                    ),
                )
            )

            results.append(
                {
                    "mal_id": manga.mal_id,
                    "title": (
                        manga.display_title
                    ),
                    "status": (
                        manga.list_status
                    ),
                    "created": created,
                    "ok": True,
                    "error": None,
                }
            )

        except Exception as error:
            results.append(
                {
                    "mal_id": (
                        tracked_entry.mal_id
                    ),
                    "title": (
                        tracked_entry
                        .title_snapshot
                        or str(
                            tracked_entry.mal_id
                        )
                    ),
                    "status": (
                        tracked_entry.status
                    ),
                    "created": False,
                    "ok": False,
                    "error": str(error),
                }
            )

    return results

