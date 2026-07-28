from decimal import Decimal

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from mal_data.models import (
    MangaEntry,
    MangaSourceLink,
)
from mal_data.services.manga_source_matching import (
    source_title_score,
)
from mal_data.services.manga_sources.registry import (
    PROVIDER_CLIENTS,
    build_provider_client,
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
            choices=sorted(PROVIDER_CLIENTS),
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
                "Saves the result at the given "
                "ranked position. For example: "
                "--save 1."
            ),
        )
        parser.add_argument(
            "--priority",
            type=int,
            help=(
                "Sets the source priority when "
                "saving. Lower values are preferred."
            ),
        )

    def handle(self, *args, **options):
        try:
            manga = MangaEntry.objects.get(
                mal_id=options["mal_id"]
            )

        except MangaEntry.DoesNotExist as error:
            raise CommandError(
                "No local MangaEntry exists "
                f"for MAL ID {options['mal_id']}."
            ) from error

        query = (
            options["query"].strip()
            or manga.title_english
            or manga.title
            or manga.title_japanese
        )

        direct_lookup = (
            query.isdigit()
            or query.startswith(
                (
                    "http://",
                    "https://",
                )
            )
        )

        score_query = query

        if direct_lookup:
            score_query = (
                manga.title_english
                or manga.title
                or manga.title_japanese
            )

        if not query:
            raise CommandError(
                "The manga has no searchable "
                "title."
            )

        provider_name = options["provider"]
        client = build_provider_client(
            provider_name
        )

        save_position = options["save"]

        if (
            save_position is not None
            and save_position < 1
        ):
            raise CommandError(
                "--save must be 1 or greater."
            )

        priority = options["priority"]

        if (
            priority is not None
            and priority < 1
        ):
            raise CommandError(
                "--priority must be 1 or greater."
            )
        

        self.stdout.write(
            f"Manga: {manga.display_title}"
        )
        self.stdout.write(
            f"MAL ID: {manga.mal_id}"
        )
        self.stdout.write(
            f"Provider: {provider_name}"
        )
        self.stdout.write(
            f"Query: {query}"
        )
        self.stdout.write("")

        try:
            candidates = client.search(query)

        except Exception as error:
            raise CommandError(
                (
                    "External source search "
                    f"failed: {error}"
                )
            ) from error

        ranked_candidates = sorted(
            (
                (
                    source_title_score(
                        score_query,
                        candidate.title,
                    ),
                    candidate,
                )
                for candidate in candidates
            ),
            key=lambda result: (
                -result[0],
                result[1].title.casefold(),
            ),
        )

        ranked_candidates = (
            ranked_candidates[
                : max(options["limit"], 1)
            ]
        )

        if not ranked_candidates:
            if save_position is not None:
                raise CommandError(
                    "No candidates were found "
                    "to save."
                )

            self.stdout.write(
                self.style.WARNING(
                    "No candidates found."
                )
            )
            return

        for position, (
            score,
            candidate,
        ) in enumerate(
            ranked_candidates,
            start=1,
        ):
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{position}. "
                        f"[{score:.2f}] "
                        f"{candidate.title}"
                    )
                )
            )
            self.stdout.write(
                f"   Source ID: "
                f"{candidate.source_id}"
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

        if save_position > len(
            ranked_candidates
        ):
            raise CommandError(
                (
                    "Cannot save result "
                    f"{save_position}. Only "
                    f"{len(ranked_candidates)} "
                    "candidate(s) were shown."
                )
            )

        score, candidate = ranked_candidates[
            save_position - 1
        ]

        source_defaults = {
            "source_id": candidate.source_id,
            "source_title": candidate.title,
            "source_url": candidate.url,
            "thumbnail_url": (
                candidate.thumbnail_url or ""
            ),
            "match_score": Decimal(
                f"{score:.2f}"
            ),
            "search_query": query,
            "active": True,
        }

        if priority is not None:
            source_defaults["priority"] = priority

        source_link, created = (
            MangaSourceLink.objects.update_or_create(
                manga=manga,
                provider=provider_name,
                defaults=source_defaults,
            )
        )

        action = (
            "Created"
            if created
            else "Updated"
        )

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
            f"   Provider: "
            f"{source_link.provider}"
        )
        self.stdout.write(
            f"   Source ID: "
            f"{source_link.source_id}"
        )
        self.stdout.write(
            f"   Source title: "
            f"{source_link.source_title}"
        )
        self.stdout.write(
            f"   Match score: "
            f"{source_link.match_score}"
        )
        self.stdout.write(
            f"   URL: "
            f"{source_link.source_url}"
        )
        self.stdout.write(
            f"   Priority: "
            f"{source_link.priority}"
        )
            