from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from mal_data.models import MangaEntry
from mal_data.services.manga_source_resolver import (
    MangaSourceLinkNotFoundError,
)
from mal_data.services.manga_source_signal_sync import (
    sync_external_chapter_signal,
)
from mal_data.services.manga_sources.registry import (
    PROVIDER_CLIENTS,
)


class Command(BaseCommand):
    help = (
        "Updates a MangaChapterSignal "
        "using a saved external source."
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
                "Uses a specific saved "
                "provider instead of the "
                "highest-priority source."
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
            result = (
                sync_external_chapter_signal(
                    manga,
                    provider=provider,
                )
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
                    "External chapter sync "
                    f"failed: {error}"
                )
            ) from error

        source_link = result[
            "source_link"
        ]
        latest_chapter = result[
            "latest_chapter"
        ]

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
        self.stdout.write("")

        if latest_chapter is None:
            self.stdout.write(
                self.style.WARNING(
                    "No chapters found. "
                    "The signal was not "
                    "modified."
                )
            )
            return

        signal = result["signal"]

        if result["created"]:
            action = "Created"

        elif result["changed"]:
            action = "Updated"

        else:
            action = "Unchanged"

        self.stdout.write(
            self.style.SUCCESS(
                f"{action} chapter signal."
            )
        )
        self.stdout.write(
            (
                "Latest chapter: "
                f"{latest_chapter.number}"
            )
        )
        self.stdout.write(
            (
                "Current progress: "
                f"{manga.num_chapters_read}"
            )
        )
        self.stdout.write(
            (
                "Pending chapters: "
                f"{signal.pending_chapters}"
            )
        )
        self.stdout.write(
            (
                "Source: "
                f"{signal.availability_source_name}"
            )
        )

        if result["used_fallback"]:
            failed_attempts = [
                attempt
                for attempt in result["attempts"]
                if not attempt["ok"]
            ]

            self.stdout.write(
                self.style.WARNING(
                    (
                        "Fallback used after "
                        f"{len(failed_attempts)} "
                        "failed source(s)."
                    )
                )
            )

