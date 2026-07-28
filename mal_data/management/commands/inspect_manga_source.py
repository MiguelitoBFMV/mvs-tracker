from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from mal_data.models import (
    MangaEntry,
    MangaSourceLink,
)
from mal_data.services.manga_sources.registry import (
    PROVIDER_CLIENTS,
    build_provider_client,
)
from mal_data.services.manga_source_resolver import (
    MangaSourceLinkNotFoundError,
    fetch_latest_saved_chapter,
)


class Command(BaseCommand):
    help = (
        "Inspects the latest chapter from "
        "a saved manga source without "
        "modifying local data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "mal_id",
            type=int,
        )

        parser.add_argument(
            "--provider",
            choices=sorted(
                PROVIDER_CLIENTS
            ),
            help=(
                "Inspects a specific saved "
                "provider instead of using "
                "the highest-priority source."
            ),
        )

    def handle(self, *args, **options):
        mal_id = options["mal_id"]
        provider = options["provider"]

        try:
            manga = MangaEntry.objects.get(
                mal_id=mal_id
            )

        except MangaEntry.DoesNotExist as error:
            raise CommandError(
                (
                    "No local MangaEntry "
                    f"exists for MAL ID "
                    f"{mal_id}."
                )
            ) from error

        try:
            (
                source_link,
                latest_chapter,
                attempts,
            ) = fetch_latest_saved_chapter(
                manga,
                provider=provider,
            )

        except (
            MangaSourceLinkNotFoundError
        ) as error:
            raise CommandError(
                str(error)
            ) from error

        except Exception as error:
            raise CommandError(
                (
                    "External chapter "
                    "inspection failed: "
                    f"{error}"
                )
            ) from error

        self.stdout.write(
            f"Manga: {manga.display_title}"
        )
        self.stdout.write(
            f"MAL ID: {manga.mal_id}"
        )
        self.stdout.write(
            (
                "Provider: "
                f"{source_link.provider}"
            )
        )
        self.stdout.write(
            (
                "Priority: "
                f"{source_link.priority}"
            )
        )
        self.stdout.write(
            (
                "Source title: "
                f"{source_link.source_title}"
            )
        )
        self.stdout.write(
            (
                "Source URL: "
                f"{source_link.source_url}"
            )
        )
        self.stdout.write("")

        if latest_chapter is None:
            self.stdout.write(
                self.style.WARNING(
                    "No chapters found."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Latest chapter: "
                    f"{latest_chapter.number}"
                )
            )
        )
        self.stdout.write(
            (
                "Label: "
                f"{latest_chapter.label}"
            )
        )
        self.stdout.write(
            (
                "Chapter URL: "
                f"{latest_chapter.url}"
            )
        )

        if latest_chapter.published_at:
            self.stdout.write(
                (
                    "Published at: "
                    f"{latest_chapter.published_at.isoformat()}"
                )
            )

        if len(attempts) > 1:
            failed_attempts = [
                attempt
                for attempt in attempts
                if not attempt["ok"]
            ]

            if failed_attempts:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        (
                            "Fallback source used "
                            f"after "
                            f"{len(failed_attempts)} "
                            "failed attempt(s)."
                        )
                    )
                )

                for attempt in failed_attempts:
                    self.stdout.write(
                        (
                            "   Failed provider: "
                            f"{attempt['provider']} · "
                            f"{attempt['error']}"
                        )
                    )