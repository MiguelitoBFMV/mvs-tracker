import copy

from django.db.models import Q
from django.utils import timezone

from mal_data.models import AnimeEntry, ManualTrackedAnime
from mal_data.services.anilist_airing_sync import (
    sync_airing_data_for_anime,
)
from mal_data.services.anime_list_sync import (
    create_sync_events,
    parse_datetime,
)
from mal_data.services.mal_client import MyAnimeListClient


def get_active_signal_entries():
    return (
        AnimeEntry.objects
        .filter(
            Q(list_status="watching")
            | Q(is_rewatching=True)
        )
        .order_by("title", "mal_id")
    )


def refresh_active_personal_status(
    anime,
    *,
    mal_client,
):
    my_list_status = (
        mal_client.fetch_anime_my_list_status(
            anime.mal_id
        )
    )

    if not my_list_status:
        return {
            "mal_id": anime.mal_id,
            "title": anime.display_title,
            "changed": False,
            "ok": False,
            "error": (
                "MAL no devolvió my_list_status "
                "para esta entrada."
            ),
        }

    previous = copy.copy(anime)

    new_values = {
        "list_status": (
            my_list_status.get("status")
            or anime.list_status
        ),
        "score": (
            my_list_status.get("score")
            or 0
        ),
        "num_episodes_watched": (
            my_list_status.get(
                "num_episodes_watched"
            )
            or 0
        ),
        "is_rewatching": bool(
            my_list_status.get("is_rewatching")
        ),
    }

    updated_at_mal = parse_datetime(
        my_list_status.get("updated_at")
    )

    if updated_at_mal is not None:
        new_values["updated_at_mal"] = (
            updated_at_mal
        )

    changed_fields = []

    for field_name, new_value in new_values.items():
        if getattr(anime, field_name) != new_value:
            setattr(anime, field_name, new_value)
            changed_fields.append(field_name)

    anime.last_synced_at = timezone.now()

    anime.save(
        update_fields=[
            *changed_fields,
            "last_synced_at",
        ]
    )

    if changed_fields:
        create_sync_events(
            anime=anime,
            previous=previous,
            created=False,
        )

    # Si la entrada es un rescate, mantenemos también
    # su fallback manual alineado con MAL.
    tracked_entry = (
        ManualTrackedAnime.objects
        .filter(
            mal_id=anime.mal_id,
            active=True,
        )
        .first()
    )

    if tracked_entry is not None:
        tracker_values = {
            "status": anime.list_status,
            "episodes_watched": (
                anime.num_episodes_watched
            ),
            "score": anime.score,
            "is_rewatching": (
                anime.is_rewatching
            ),
        }

        tracker_changed_fields = []

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

    return {
        "mal_id": anime.mal_id,
        "title": anime.display_title,
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "ok": True,
        "error": None,
    }


def sync_episode_signals_complete():
    mal_client = MyAnimeListClient()

    original_targets = list(
        get_active_signal_entries()
    )

    personal_results = []

    for anime in original_targets:
        try:
            result = refresh_active_personal_status(
                anime,
                mal_client=mal_client,
            )

        except Exception as error:
            result = {
                "mal_id": anime.mal_id,
                "title": anime.display_title,
                "changed": False,
                "ok": False,
                "error": str(error),
            }

        personal_results.append(result)

    # Volvemos a consultar después de actualizar MAL.
    # Si alguno pasó a Completed y ya no es rewatch,
    # deja de formar parte de Episode Signals.
    active_targets = list(
        get_active_signal_entries()
    )

    airing_results = []

    for anime in active_targets:
        try:
            airing_data, created = (
                sync_airing_data_for_anime(
                    anime.mal_id
                )
            )

            airing_results.append(
                {
                    "mal_id": anime.mal_id,
                    "title": anime.display_title,
                    "created": created,
                    "pending": (
                        airing_data
                        .pending_episodes_for_user
                    ),
                    "ok": True,
                    "error": None,
                }
            )

        except Exception as error:
            airing_results.append(
                {
                    "mal_id": anime.mal_id,
                    "title": anime.display_title,
                    "created": False,
                    "pending": 0,
                    "ok": False,
                    "error": str(error),
                }
            )

    return {
        "personal": personal_results,
        "airing": airing_results,
    }

