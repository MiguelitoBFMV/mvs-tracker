from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from mal_data.models import MangaEntry
from mal_data.services.manga_source_search import (
    get_candidate_by_position,
    save_manga_source_candidate,
    search_manga_sources,
)
from mal_data.services.manga_sources.registry import (
    PROVIDER_CLIENTS,
)


class Command(BaseCommand):
    help = (
        "Searches external manga sources "
        "and optionally saves one result."
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
            default="weeb_central",
        )

        parser.add_argument(
            "--query",
            default="",
            help=(
                "Overrides the title used "
                "for the search."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=10,
        )

        parser.add_argument(
            "--save",
            type=int,
            metavar="POSITION",
            help=(
                "Saves the result at the "
                "given ranked position."
            ),
        )

        parser.add_argument(
            "--priority",
            type=int,
            help=(
                "Sets the source priority "
                "when saving. Lower values "
                "are preferred."
            ),
        )

    def handle(self, *args, **options):
        try:
            manga = MangaEntry.objects.get(
                mal_id=options["mal_id"]
            )

        except MangaEntry.DoesNotExist as error:
            raise CommandError(
                (
                    "No local MangaEntry "
                    "exists for MAL ID "
                    f"{options['mal_id']}."
                )
            ) from error

        save_position = options["save"]
        priority = options["priority"]

        if (
            save_position is not None
            and save_position < 1
        ):
            raise CommandError(
                "--save must be 1 or greater."
            )

        if (
            priority is not None
            and priority < 1
        ):
            raise CommandError(
                "--priority must be "
                "1 or greater."
            )

        try:
            search_result = (
                search_manga_sources(
                    manga,
                    provider=(
                        options["provider"]
                    ),
                    query=options["query"],
                    limit=options["limit"],
                )
            )

        except Exception as error:
            raise CommandError(
                (
                    "External source search "
                    f"failed: {error}"
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
                f"{search_result.provider}"
            )
        )
        self.stdout.write(
            (
                "Query: "
                f"{search_result.query}"
            )
        )
        self.stdout.write("")

        if not search_result.candidates:
            if save_position is not None:
                raise CommandError(
                    "No candidates were "
                    "found to save."
                )

            self.stdout.write(
                self.style.WARNING(
                    "No candidates found."
                )
            )
            return

        for candidate in (
            search_result.candidates
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{candidate.position}. "
                        f"[{candidate.score}] "
                        f"{candidate.title}"
                    )
                )
            )

            self.stdout.write(
                (
                    "   Source ID: "
                    f"{candidate.source_id}"
                )
            )
            self.stdout.write(
                f"   URL: {candidate.url}"
            )

            if candidate.thumbnail_url:
                self.stdout.write(
                    (
                        "   Cover: "
                        f"{candidate.thumbnail_url}"
                    )
                )

            self.stdout.write("")

        if save_position is None:
            return

        try:
            selected_candidate = (
                get_candidate_by_position(
                    search_result,
                    save_position,
                )
            )

            source_link, created = (
                save_manga_source_candidate(
                    manga,
                    provider=(
                        search_result.provider
                    ),
                    candidate=(
                        selected_candidate
                    ),
                    search_query=(
                        search_result.query
                    ),
                    priority=priority,
                )
            )

        except ValueError as error:
            raise CommandError(
                str(error)
            ) from error

        action = (
            "Created"
            if created
            else "Updated"
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} source link:"
            )
        )
        self.stdout.write(
            f"   Manga: {manga.title}"
        )
        self.stdout.write(
            (
                "   Provider: "
                f"{source_link.provider}"
            )
        )
        self.stdout.write(
            (
                "   Source ID: "
                f"{source_link.source_id}"
            )
        )
        self.stdout.write(
            (
                "   Source title: "
                f"{source_link.source_title}"
            )
        )
        self.stdout.write(
            (
                "   Match score: "
                f"{source_link.match_score}"
            )
        )
        self.stdout.write(
            (
                "   Priority: "
                f"{source_link.priority}"
            )
        )
        self.stdout.write(
            (
                "   Official: "
                f"{source_link.is_official}"
            )
        )
        self.stdout.write(
            f"   URL: {source_link.source_url}"
        )

