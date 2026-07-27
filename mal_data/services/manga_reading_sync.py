import copy

from django.db.models import Q
from django.utils import timezone

from mal_data.models import (
    MangaEntry,
    ManualTrackedManga,
)
from mal_data.services.mal_client import (
    MyAnimeListClient,
)
from mal_data.services.manga_list_sync import (
    build_manga_defaults,
    create_manga_sync_events,
    parse_datetime,
)
from mal_data.services.manual_tracked_manga_sync import (
    sync_manual_tracked_manga_entry,
)


PERSONAL_SYNC_FIELDS = (
    "list_status",
    "score",
    "num_volumes_read",
    "num_chapters_read",
    "is_rereading",
    "updated_at_mal",
)


def get_active_reading_entries():
    return (
        MangaEntry.objects
        .filter(
            Q(list_status="reading")
            | Q(is_rereading=True)
        )
        .order_by("title", "mal_id")
    )


def align_manual_tracker(manga):
    tracked_entry = (
        ManualTrackedManga.objects
        .filter(
            mal_id=manga.mal_id,
            active=True,
        )
        .first()
    )

    if tracked_entry is None:
        return False

    tracker_values = {
        "title_snapshot": manga.display_title,
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
    }

    changed_fields = []

    for field_name, new_value in (
        tracker_values.items()
    ):
        if (
            getattr(tracked_entry, field_name)
            != new_value
        ):
            setattr(
                tracked_entry,
                field_name,
                new_value,
            )
            changed_fields.append(field_name)

    if changed_fields:
        tracked_entry.save(
            update_fields=[
                *changed_fields,
                "updated_at",
            ]
        )

    return bool(changed_fields)


def apply_personal_values(
    manga,
    new_values,
):
    previous = copy.copy(manga)
    changed_fields = []

    for field_name in PERSONAL_SYNC_FIELDS:
        if field_name not in new_values:
            continue

        new_value = new_values[field_name]

        if (
            getattr(manga, field_name)
            != new_value
        ):
            setattr(
                manga,
                field_name,
                new_value,
            )
            changed_fields.append(field_name)

    manga.last_synced_at = timezone.now()

    manga.save(
        update_fields=[
            *changed_fields,
            "last_synced_at",
        ]
    )

    if changed_fields:
        create_manga_sync_events(
            manga=manga,
            previous=previous,
            created=False,
        )

    align_manual_tracker(manga)

    return changed_fields


def build_personal_values_from_status(
    manga,
    my_list_status,
):
    values = {
        "list_status": (
            my_list_status.get("status")
            or manga.list_status
        ),
        "score": (
            my_list_status.get("score")
            or 0
        ),
        "num_volumes_read": (
            my_list_status.get(
                "num_volumes_read"
            )
            or 0
        ),
        "num_chapters_read": (
            my_list_status.get(
                "num_chapters_read"
            )
            or 0
        ),
        "is_rereading": bool(
            my_list_status.get(
                "is_rereading"
            )
        ),
    }

    updated_at_mal = parse_datetime(
        my_list_status.get("updated_at")
    )

    if updated_at_mal is not None:
        values["updated_at_mal"] = (
            updated_at_mal
        )

    return values


def sync_reading_list_item(item):
    node = item.get("node") or {}
    mal_id = node.get("id")

    if mal_id is None:
        raise ValueError(
            "Manga sin MAL ID en la lista "
            "Reading."
        )

    sync_time = timezone.now()

    normalized_mal_id, defaults = (
        build_manga_defaults(
            item,
            sync_time=sync_time,
        )
    )

    manga = (
        MangaEntry.objects
        .filter(mal_id=normalized_mal_id)
        .first()
    )

    if manga is None:
        manga = MangaEntry.objects.create(
            mal_id=normalized_mal_id,
            **defaults,
        )

        create_manga_sync_events(
            manga=manga,
            previous=None,
            created=True,
        )

        align_manual_tracker(manga)

        return {
            "mal_id": manga.mal_id,
            "title": manga.display_title,
            "source": "reading_list",
            "created": True,
            "changed": True,
            "changed_fields": [
                "created",
            ],
            "ok": True,
            "error": None,
        }

    personal_values = {
        field_name: defaults[field_name]
        for field_name
        in PERSONAL_SYNC_FIELDS
    }

    changed_fields = apply_personal_values(
        manga,
        personal_values,
    )

    return {
        "mal_id": manga.mal_id,
        "title": manga.display_title,
        "source": "reading_list",
        "created": False,
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "ok": True,
        "error": None,
    }


def refresh_individual_status(
    manga,
    *,
    mal_client,
    source,
):
    my_list_status = (
        mal_client.fetch_manga_my_list_status(
            manga.mal_id
        )
    )

    if not my_list_status:
        return {
            "mal_id": manga.mal_id,
            "title": manga.display_title,
            "source": source,
            "created": False,
            "changed": False,
            "changed_fields": [],
            "ok": False,
            "error": (
                "MAL no devolvió "
                "my_list_status."
            ),
        }

    personal_values = (
        build_personal_values_from_status(
            manga,
            my_list_status,
        )
    )

    changed_fields = apply_personal_values(
        manga,
        personal_values,
    )

    return {
        "mal_id": manga.mal_id,
        "title": manga.display_title,
        "source": source,
        "created": False,
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "ok": True,
        "error": None,
    }


def sync_reading_progress():
    mal_client = MyAnimeListClient()

    original_active_entries = list(
        get_active_reading_entries()
    )

    original_active_by_id = {
        manga.mal_id: manga
        for manga in original_active_entries
    }

    active_trackers = list(
        ManualTrackedManga.objects
        .filter(active=True)
    )

    active_tracker_ids = {
        tracker.mal_id
        for tracker in active_trackers
    }

    manual_target_ids = {
        tracker.mal_id
        for tracker in active_trackers
        if (
            tracker.status == "reading"
            or tracker.is_rereading
            or tracker.mal_id
            in original_active_by_id
        )
    }

    results = []
    reading_api_ids = set()
    list_checked = 0

    # Primera fuente:
    # una sola lista MAL status=reading.
    for page_data in (
        mal_client.fetch_all_manga_by_status(
            "reading"
        )
    ):
        for item in page_data.get(
            "entries",
            [],
        ):
            list_checked += 1

            node = item.get("node") or {}
            mal_id = node.get("id")

            if mal_id is not None:
                reading_api_ids.add(mal_id)

            try:
                result = sync_reading_list_item(
                    item
                )

            except Exception as error:
                result = {
                    "mal_id": mal_id,
                    "title": (
                        node.get("title")
                        or str(mal_id)
                    ),
                    "source": "reading_list",
                    "created": False,
                    "changed": False,
                    "changed_fields": [],
                    "ok": False,
                    "error": str(error),
                }

            results.append(result)

    manual_checked = 0

    # Segunda fuente:
    # rescates omitidos por la lista general.
    for mal_id in sorted(
        manual_target_ids
        - reading_api_ids
    ):
        manual_checked += 1

        tracked_entry = (
            ManualTrackedManga.objects
            .filter(
                mal_id=mal_id,
                active=True,
            )
            .first()
        )

        if tracked_entry is None:
            continue

        manga = (
            MangaEntry.objects
            .filter(mal_id=mal_id)
            .first()
        )

        try:
            if manga is None:
                manga, created = (
                    sync_manual_tracked_manga_entry(
                        tracked_entry,
                        mal_client=mal_client,
                    )
                )

                result = {
                    "mal_id": manga.mal_id,
                    "title": (
                        manga.display_title
                    ),
                    "source": "manual_rescue",
                    "created": created,
                    "changed": True,
                    "changed_fields": [
                        "created",
                    ],
                    "ok": True,
                    "error": None,
                }

            else:
                result = (
                    refresh_individual_status(
                        manga,
                        mal_client=mal_client,
                        source="manual_rescue",
                    )
                )

        except Exception as error:
            result = {
                "mal_id": mal_id,
                "title": (
                    tracked_entry.title_snapshot
                    or str(mal_id)
                ),
                "source": "manual_rescue",
                "created": False,
                "changed": False,
                "changed_fields": [],
                "ok": False,
                "error": str(error),
            }

        results.append(result)

    reconciled_checked = 0

    # Tercera fuente:
    # Reading normales que ya no aparecen en
    # status=reading. Solo estos necesitan una
    # consulta individual para conocer su nuevo
    # estado.
    missing_normal_ids = (
        set(original_active_by_id)
        - reading_api_ids
        - active_tracker_ids
    )

    for mal_id in sorted(missing_normal_ids):
        reconciled_checked += 1

        manga = original_active_by_id[mal_id]

        try:
            result = refresh_individual_status(
                manga,
                mal_client=mal_client,
                source="status_reconciliation",
            )

        except Exception as error:
            result = {
                "mal_id": manga.mal_id,
                "title": manga.display_title,
                "source": (
                    "status_reconciliation"
                ),
                "created": False,
                "changed": False,
                "changed_fields": [],
                "ok": False,
                "error": str(error),
            }

        results.append(result)

    return {
        "personal": results,
        "list_checked": list_checked,
        "manual_checked": manual_checked,
        "reconciled_checked": (
            reconciled_checked
        ),
        "active_after": (
            get_active_reading_entries()
            .count()
        ),
    }


