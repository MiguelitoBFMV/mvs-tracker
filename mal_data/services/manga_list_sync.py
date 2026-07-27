import copy
import json

from urllib.parse import urlsplit
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from mal_data.models import (
    MangaEntry,
    MangaSyncEvent,
)
from mal_data.services.mal_client import (
    MyAnimeListClient,
)


VALID_MANGA_STATUSES = (
    "reading",
    "completed",
    "on_hold",
    "dropped",
    "plan_to_read",
)


SYNC_COMPARE_FIELDS = (
    "title",
    "title_japanese",
    "title_english",
    "main_picture_url",
    "media_type",
    "publication_status",
    "num_volumes",
    "num_chapters",
    "start_date",
    "end_date",
    "list_status",
    "score",
    "num_volumes_read",
    "num_chapters_read",
    "is_rereading",
    "updated_at_mal",
)

PICTURE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".webp",
)


def picture_resource_key(value):
    if not value:
        return value

    parsed_url = urlsplit(value)
    resource_path = parsed_url.path
    lowered_path = resource_path.lower()

    for extension in PICTURE_EXTENSIONS:
        if lowered_path.endswith(extension):
            resource_path = resource_path[
                :-len(extension)
            ]
            break

    return (
        parsed_url.scheme,
        parsed_url.netloc,
        resource_path,
    )


def manga_field_changed(
    field_name,
    current_value,
    incoming_value,
):
    if field_name == "main_picture_url":
        return (
            picture_resource_key(current_value)
            != picture_resource_key(
                incoming_value
            )
        )

    return current_value != incoming_value


def build_manga_defaults(
    item,
    *,
    sync_time=None,
):
    node = item.get("node", {})
    list_status = item.get("list_status", {})
    main_picture = (
        node.get("main_picture") or {}
    )
    alternative_titles = (
        node.get("alternative_titles") or {}
    )

    mal_id = node.get("id")

    if mal_id is None:
        raise ValueError(
            "Manga sin MAL ID en respuesta de API."
        )

    return mal_id, {
        "title": node.get("title") or "",
        "title_japanese": (
            alternative_titles.get("ja")
        ),
        "title_english": (
            alternative_titles.get("en")
        ),
        "main_picture_url": (
            main_picture.get("large")
            or main_picture.get("medium")
        ),
        "media_type": node.get("media_type"),
        "publication_status": node.get("status"),
        "num_volumes": (
            node.get("num_volumes") or 0
        ),
        "num_chapters": (
            node.get("num_chapters") or 0
        ),
        "start_date": parse_date(
            node.get("start_date")
        ),
        "end_date": parse_date(
            node.get("end_date")
        ),
        "list_status": (
            list_status.get("status") or ""
        ),
        "score": (
            list_status.get("score") or 0
        ),
        "num_volumes_read": (
            list_status.get("num_volumes_read")
            or 0
        ),
        "num_chapters_read": (
            list_status.get("num_chapters_read")
            or 0
        ),
        "is_rereading": (
            list_status.get("is_rereading")
            or False
        ),
        "updated_at_mal": parse_datetime(
            list_status.get("updated_at")
        ),
        "raw_data": item,
        "last_synced_at": (
            sync_time or timezone.now()
        ),
    }


def sync_manga_status(
    status,
    *,
    save_raw=True,
    client=None,
):
    if status not in VALID_MANGA_STATUSES:
        raise ValueError(
            f"Estado de manga inválido: {status}"
        )

    client = client or MyAnimeListClient()

    all_entries = []

    for page_data in (
        client.fetch_all_manga_by_status(
            status
        )
    ):
        entries = page_data.get("entries", [])
        all_entries.extend(entries)

    if save_raw:
        save_raw_json(
            status,
            all_entries,
        )

    sync_time = timezone.now()

    normalized_entries = []
    mal_ids = []

    for item in all_entries:
        mal_id, defaults = build_manga_defaults(
            item,
            sync_time=sync_time,
        )

        normalized_entries.append(
            (
                item,
                mal_id,
                defaults,
            )
        )
        mal_ids.append(mal_id)

    existing_by_mal_id = (
        MangaEntry.objects.in_bulk(
            mal_ids,
            field_name="mal_id",
        )
    )

    created_count = 0
    updated_count = 0
    unchanged_count = 0
    unchanged_ids = []

    with transaction.atomic():
        for (
            item,
            mal_id,
            defaults,
        ) in normalized_entries:
            manga = existing_by_mal_id.get(
                mal_id
            )

            if manga is None:
                manga = MangaEntry.objects.create(
                    mal_id=mal_id,
                    **defaults,
                )

                create_manga_sync_events(
                    manga=manga,
                    previous=None,
                    created=True,
                )

                created_count += 1
                continue

            previous = copy.copy(manga)
            
            changed_fields = [
                field_name
                for field_name
                in SYNC_COMPARE_FIELDS
                if manga_field_changed(
                    field_name,
                    getattr(manga, field_name),
                    defaults[field_name],
                )
            ]

            if not changed_fields:
                unchanged_count += 1
                unchanged_ids.append(mal_id)
                continue

            for field_name in changed_fields:
                setattr(
                    manga,
                    field_name,
                    defaults[field_name],
                )

            manga.raw_data = item
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
                update_fields=update_fields,
            )

            create_manga_sync_events(
                manga=manga,
                previous=previous,
                created=False,
            )

            updated_count += 1

        if unchanged_ids:
            MangaEntry.objects.filter(
                mal_id__in=unchanged_ids
            ).update(
                last_synced_at=sync_time
            )

    return {
        "status": status,
        "total": len(all_entries),
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
    }


def sync_all_manga_statuses(
    *,
    save_raw=True,
):
    client = MyAnimeListClient()
    results = []

    for status in VALID_MANGA_STATUSES:
        result = sync_manga_status(
            status,
            save_raw=save_raw,
            client=client,
        )
        results.append(result)

    return results


def save_raw_json(status, entries):
    raw_dir = (
        settings.BASE_DIR
        / "data"
        / "raw"
    )
    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = (
        raw_dir
        / f"manga_{status}_{timestamp}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            entries,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


def create_manga_sync_events(
    manga,
    previous,
    created,
):
    if created:
        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.display_title,
            event_type="created",
            old_value="not_in_local_db",
            new_value=manga.list_status,
        )
        return

    if previous is None:
        return

    status_changed = (
        previous.list_status
        != manga.list_status
        or previous.is_rereading
        != manga.is_rereading
    )

    if status_changed:
        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.display_title,
            event_type="status_changed",
            old_value=(
                previous.personal_status_label
            ),
            new_value=(
                manga.personal_status_label
            ),
        )

    if (
        previous.num_chapters_read
        != manga.num_chapters_read
    ):
        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.display_title,
            event_type="chapter_changed",
            old_value=(
                f"CH. "
                f"{previous.num_chapters_read}"
            ),
            new_value=(
                f"CH. "
                f"{manga.num_chapters_read}"
            ),
        )

    if (
        previous.num_volumes_read
        != manga.num_volumes_read
    ):
        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.display_title,
            event_type="volume_changed",
            old_value=(
                f"VOL. "
                f"{previous.num_volumes_read}"
            ),
            new_value=(
                f"VOL. "
                f"{manga.num_volumes_read}"
            ),
        )

    if previous.score != manga.score:
        MangaSyncEvent.objects.create(
            manga=manga,
            mal_id=manga.mal_id,
            title_snapshot=manga.display_title,
            event_type="score_changed",
            old_value=(
                f"Score {previous.score}"
            ),
            new_value=f"Score {manga.score}",
        )


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


