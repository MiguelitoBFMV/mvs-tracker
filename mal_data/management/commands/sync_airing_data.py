from django.core.management.base import BaseCommand

from mal_data.services.anilist_airing_sync import (
    sync_airing_data_for_anime,
    sync_airing_data_for_dashboard,
)


class Command(BaseCommand):
    help = "Sincroniza datos de emisión desde AniList usando MAL ID."

    def add_arguments(self, parser):
        parser.add_argument(
            "mal_id",
            nargs="?",
            type=int,
            help="MAL ID específico.",
        )
        parser.add_argument(
            "--dashboard",
            action="store_true",
            help="Sincroniza watching y plan_to_watch actualmente en emisión.",
        )

    def handle(self, *args, **options):
        mal_id = options.get("mal_id")
        dashboard = options.get("dashboard")

        if dashboard:
            self.stdout.write(
                self.style.WARNING("Sincronizando datos AniList para dashboard...")
            )

            results = sync_airing_data_for_dashboard()

            ok_count = sum(1 for result in results if result["ok"])
            error_count = sum(1 for result in results if not result["ok"])

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Sync AniList completado"))
            self.stdout.write(f"OK: {ok_count}")
            self.stdout.write(f"Errores: {error_count}")

            for result in results:
                if result["ok"]:
                    self.stdout.write(
                        f"- {result['title']} · pending={result['pending']}"
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"- {result['title']} · ERROR: {result['error']}"
                        )
                    )

            return

        if mal_id is None:
            self.stdout.write(
                self.style.ERROR(
                    "Debes indicar un MAL ID o usar --dashboard."
                )
            )
            return

        airing_data, created = sync_airing_data_for_anime(mal_id)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Datos AniList sincronizados"))
        self.stdout.write(f"Anime: {airing_data.anime.display_title}")
        self.stdout.write(f"AniList ID: {airing_data.anilist_id}")
        self.stdout.write(f"Status: {airing_data.anilist_status}")
        self.stdout.write(f"Estimated aired: {airing_data.episodes_aired_estimated}")
        self.stdout.write(f"Next episode: {airing_data.next_airing_episode}")
        self.stdout.write(f"Pending for you: {airing_data.pending_episodes_for_user}")
        self.stdout.write(f"Created: {created}")