from django.utils import timezone

from mal_data.models import AnimeEntry, ManualTrackedAnime
from mal_data.services.anime_list_sync import (
    create_sync_events,
    parse_date,
    parse_datetime,
)
from mal_data.services.mal_client import MyAnimeListClient


def sync_manual_tracked_anime_entry(tracked_entry):
    client = MyAnimeListClient()

    details = client.fetch_anime_details(
        tracked_entry.mal_id
    )

    # Aunque el endpoint general de lista omita el anime,
    # el detalle individual puede devolver su estado real en MAL.
    my_list_status = client.fetch_anime_my_list_status(
        tracked_entry.mal_id
    )

    if my_list_status:
        resolved_status = (
            my_list_status.get("status")
            or tracked_entry.status
        )
        resolved_episodes_watched = (
            my_list_status.get("num_episodes_watched")
            or 0
        )
        resolved_score = (
            my_list_status.get("score")
            or 0
        )
        resolved_is_rewatching = bool(
            my_list_status.get("is_rewatching")
        )
        resolved_updated_at = (
            parse_datetime(
                my_list_status.get("updated_at")
            )
            or timezone.now()
        )
    else:
        # Fallback para casos donde MAL tampoco entregue
        # my_list_status desde el detalle individual.
        resolved_status = tracked_entry.status
        resolved_episodes_watched = (
            tracked_entry.episodes_watched
        )
        resolved_score = tracked_entry.score
        resolved_is_rewatching = (
            tracked_entry.is_rewatching
        )
        resolved_updated_at = timezone.now()

    main_picture = details.get("main_picture") or {}
    alternative_titles = (
        details.get("alternative_titles") or {}
    )

    previous = AnimeEntry.objects.filter(
        mal_id=tracked_entry.mal_id
    ).first()

    anime, created = AnimeEntry.objects.update_or_create(
        mal_id=tracked_entry.mal_id,
        defaults={
            "title": (
                details.get("title")
                or tracked_entry.title_snapshot
                or ""
            ),
            "title_japanese": alternative_titles.get("ja"),
            "title_english": alternative_titles.get("en"),
            "main_picture_url": (
                main_picture.get("large")
                or main_picture.get("medium")
            ),
            "media_type": details.get("media_type"),
            "airing_status": details.get("status"),
            "num_episodes": (
                details.get("num_episodes")
                or 0
            ),
            "start_date": parse_date(
                details.get("start_date")
            ),
            "end_date": parse_date(
                details.get("end_date")
            ),
            "list_status": resolved_status,
            "score": resolved_score,
            "num_episodes_watched": (
                resolved_episodes_watched
            ),
            "is_rewatching": (
                resolved_is_rewatching
            ),
            "updated_at_mal": resolved_updated_at,
            "raw_data": {
                "source": "manual_tracked_sync",
                "details": details,
                "my_list_status": my_list_status,
                "manual_fallback": {
                    "status": tracked_entry.status,
                    "episodes_watched": (
                        tracked_entry.episodes_watched
                    ),
                    "score": tracked_entry.score,
                    "is_rewatching": (
                        tracked_entry.is_rewatching
                    ),
                },
            },
            "last_synced_at": timezone.now(),
        },
    )

    # Manual rescues ahora también generan Command Logs.
    create_sync_events(
        anime=anime,
        previous=previous,
        created=created,
    )

    # Mantener el tracker alineado con MAL para que también
    # sirva como fallback actualizado.
    tracker_changed_fields = []

    tracker_values = {
        "title_snapshot": anime.display_title,
        "status": resolved_status,
        "episodes_watched": resolved_episodes_watched,
        "score": resolved_score,
        "is_rewatching": resolved_is_rewatching,
    }

    for field_name, new_value in tracker_values.items():
        if getattr(tracked_entry, field_name) != new_value:
            setattr(tracked_entry, field_name, new_value)
            tracker_changed_fields.append(field_name)

    if tracker_changed_fields:
        tracked_entry.save(
            update_fields=[
                *tracker_changed_fields,
                "updated_at",
            ]
        )

    return anime, created


def sync_manual_tracked_anime_entries():
    tracked_entries = (
        ManualTrackedAnime.objects
        .filter(active=True)
        .order_by("title_snapshot", "mal_id")
    )

    results = []

    for tracked_entry in tracked_entries:
        try:
            anime, created = (
                sync_manual_tracked_anime_entry(
                    tracked_entry
                )
            )

            results.append(
                {
                    "mal_id": tracked_entry.mal_id,
                    "title": anime.display_title,
                    "created": created,
                    "ok": True,
                    "error": None,
                }
            )

        except Exception as error:
            results.append(
                {
                    "mal_id": tracked_entry.mal_id,
                    "title": (
                        tracked_entry.title_snapshot
                        or f"MAL ID {tracked_entry.mal_id}"
                    ),
                    "created": False,
                    "ok": False,
                    "error": str(error),
                }
            )

    return results
