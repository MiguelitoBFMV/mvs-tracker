from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from mal_data.models import AnimeEntry
from mal_data.services.anilist_client import AniListClient


class Command(BaseCommand):
    help = "Inspecciona datos públicos de airing desde AniList usando MAL ID."

    def add_arguments(self, parser):
        parser.add_argument(
            "mal_id",
            type=int,
            help="MAL ID del anime.",
        )

    def handle(self, *args, **options):
        mal_id = options["mal_id"]

        local_anime = AnimeEntry.objects.filter(mal_id=mal_id).first()

        if local_anime:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("LOCAL MAL DATA"))
            self.stdout.write(f"Title: {local_anime.display_title}")
            self.stdout.write(f"MAL ID: {local_anime.mal_id}")
            self.stdout.write(f"List status: {local_anime.personal_status_label}")
            self.stdout.write(
                f"Progress: {local_anime.num_episodes_watched}/{local_anime.num_episodes or 'TBD'}"
            )
            self.stdout.write(f"Airing status: {local_anime.airing_status}")
        else:
            self.stdout.write(
                self.style.WARNING(f"No existe AnimeEntry local para MAL ID {mal_id}")
            )

        client = AniListClient()
        media = client.fetch_anime_by_mal_id(mal_id)

        if not media:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("AniList no encontró este MAL ID."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("ANILIST DATA"))
        self.stdout.write(f"AniList ID: {media.get('id')}")
        self.stdout.write(f"MAL ID: {media.get('idMal')}")
        self.stdout.write(f"Romaji: {media.get('title', {}).get('romaji')}")
        self.stdout.write(f"English: {media.get('title', {}).get('english')}")
        self.stdout.write(f"Native: {media.get('title', {}).get('native')}")
        self.stdout.write(f"Status: {media.get('status')}")
        self.stdout.write(f"Episodes: {media.get('episodes') or 'TBD'}")

        next_airing = media.get("nextAiringEpisode")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("NEXT AIRING EPISODE"))

        if next_airing:
            episode = next_airing.get("episode")
            aired_estimate = episode - 1 if episode else None

            self.stdout.write(f"Next episode: {episode}")
            self.stdout.write(f"Estimated aired episodes: {aired_estimate}")
            self.stdout.write(
                f"Airing at: {format_timestamp(next_airing.get('airingAt'))}"
            )
            self.stdout.write(
                f"Time until airing: {format_seconds(next_airing.get('timeUntilAiring'))}"
            )

            if local_anime and aired_estimate is not None:
                pending = aired_estimate - local_anime.num_episodes_watched
                pending = max(pending, 0)

                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS("PERSONAL SIGNAL"))
                self.stdout.write(f"Watched in MAL: {local_anime.num_episodes_watched}")
                self.stdout.write(f"Estimated aired: {aired_estimate}")
                self.stdout.write(f"Pending episodes for you: {pending}")
        else:
            self.stdout.write("No nextAiringEpisode disponible.")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("UPCOMING SCHEDULE"))

        schedule_nodes = (
            media.get("airingSchedule", {})
            .get("nodes", [])
        )

        if schedule_nodes:
            for node in schedule_nodes:
                self.stdout.write(
                    f"EP {node.get('episode')} · "
                    f"{format_timestamp(node.get('airingAt'))} · "
                    f"{format_seconds(node.get('timeUntilAiring'))}"
                )
        else:
            self.stdout.write("No airingSchedule futuro disponible.")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("EXTERNAL LINKS"))

        external_links = media.get("externalLinks") or []

        if external_links:
            for link in external_links[:15]:
                self.stdout.write(
                    f"{link.get('site')} · "
                    f"type={link.get('type')} · "
                    f"lang={link.get('language')} · "
                    f"{link.get('url')}"
                )
        else:
            self.stdout.write("No externalLinks disponibles.")

        self.stdout.write("")
        self.stdout.write(self.style.WARNING("STREAMING EPISODES"))

        streaming_episodes = media.get("streamingEpisodes") or []

        if streaming_episodes:
            for episode in streaming_episodes[:10]:
                self.stdout.write(
                    f"{episode.get('site')} · "
                    f"{episode.get('title')} · "
                    f"{episode.get('url')}"
                )
        else:
            self.stdout.write("No streamingEpisodes disponibles.")


def format_timestamp(value):
    if not value:
        return "N/A"

    dt = datetime.fromtimestamp(value, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def format_seconds(value):
    if value is None:
        return "N/A"

    days = value // 86400
    hours = (value % 86400) // 3600
    minutes = (value % 3600) // 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m"

    if hours > 0:
        return f"{hours}h {minutes}m"

    return f"{minutes}m"