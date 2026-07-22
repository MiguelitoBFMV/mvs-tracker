from datetime import datetime, timezone as datetime_timezone
from django.db.models import Q
from django.utils import timezone

from mal_data.models import AnimeAiringData, AnimeEntry
from mal_data.services.anilist_client import AniListClient


def sync_airing_data_for_anime(mal_id):
    anime = AnimeEntry.objects.filter(mal_id=mal_id).first()

    if not anime:
        raise ValueError(f"No existe AnimeEntry local para MAL ID {mal_id}")

    client = AniListClient()
    media = client.fetch_anime_by_mal_id(mal_id)

    if not media:
        raise ValueError(f"AniList no encontró data para MAL ID {mal_id}")

    title = media.get("title") or {}
    next_airing = media.get("nextAiringEpisode") or {}

    next_episode = next_airing.get("episode")
    anilist_episodes = media.get("episodes") or 0
    episodes_aired_estimated = 0

    if next_episode:
        episodes_aired_estimated = max(next_episode - 1, 0)
    elif anilist_episodes and (
        media.get("status") == "FINISHED"
        or anime.airing_status == "finished_airing"
    ):
        episodes_aired_estimated = anilist_episodes

    external_links = media.get("externalLinks") or []
    streaming_links = [
        {
            "site": link.get("site"),
            "url": link.get("url"),
            "type": link.get("type"),
            "language": link.get("language"),
        }
        for link in external_links
        if link.get("type") == "STREAMING"
    ]

    streaming_episodes = media.get("streamingEpisodes") or []

    airing_data, created = AnimeAiringData.objects.update_or_create(
        mal_id=mal_id,
        defaults={
            "anime": anime,
            "anilist_id": media.get("id"),
            "title_romaji": title.get("romaji"),
            "title_english": title.get("english"),
            "title_native": title.get("native"),
            "anilist_status": media.get("status"),
            "anilist_episodes": anilist_episodes,
            "next_airing_episode": next_episode,
            "next_airing_at": parse_anilist_timestamp(next_airing.get("airingAt")),
            "time_until_airing_seconds": next_airing.get("timeUntilAiring"),
            "episodes_aired_estimated": episodes_aired_estimated,
            "streaming_links": streaming_links,
            "streaming_episodes": streaming_episodes,
            "raw_data": media,
            "last_synced_at": timezone.now(),
        },
    )

    return airing_data, created

def sync_episode_signals():
    targets = (
        AnimeEntry.objects
        .filter(
            Q(list_status="watching")
            | Q(
                list_status="completed",
                is_rewatching=True,
            )
        )
        .order_by("title")
    )

    results = []

    for anime in targets:
        try:
            airing_data, created = sync_airing_data_for_anime(
                anime.mal_id
            )

            results.append(
                {
                    "mal_id": anime.mal_id,
                    "title": anime.display_title,
                    "created": created,
                    "pending": (
                        airing_data.pending_episodes_for_user
                    ),
                    "ok": True,
                    "error": None,
                }
            )

        except Exception as error:
            results.append(
                {
                    "mal_id": anime.mal_id,
                    "title": anime.display_title,
                    "created": False,
                    "pending": 0,
                    "ok": False,
                    "error": str(error),
                }
            )

    return results


def sync_airing_data_for_dashboard():
    """
    Alias temporal para mantener compatibilidad con comandos
    o servicios que todavía usen el nombre antiguo.
    """
    return sync_episode_signals()

def parse_anilist_timestamp(value):
    if not value:
        return None

    return datetime.fromtimestamp(value, tz=datetime_timezone.utc)