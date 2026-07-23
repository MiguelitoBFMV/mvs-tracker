from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import (
    Exists,
    OuterRef,
    Prefetch,
)

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


class Command(BaseCommand):
    help = (
        "Create Playthrough 1 for completed library "
        "entries that do not have playthrough history."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show which playthroughs would be created "
                "without modifying the database."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        existing_playthroughs = (
            Playthrough.objects.filter(
                library_entry=OuterRef("pk"),
            )
        )

        owned_accesses = (
            GameAccess.objects
            .filter(
                access_type=GameAccess.AccessType.OWNED,
            )
            .order_by(
                "created_at",
                "pk",
            )
        )

        candidate_queryset = (
            LibraryEntry.objects
            .select_related(
                "game",
            )
            .annotate(
                has_playthrough=Exists(
                    existing_playthroughs
                ),
            )
            .filter(
                status=LibraryEntry.Status.COMPLETED,
                has_playthrough=False,
            )
            .prefetch_related(
                Prefetch(
                    "accesses",
                    queryset=owned_accesses,
                    to_attr="owned_accesses",
                )
            )
            .order_by(
                "game__title",
            )
        )

        candidate_ids = list(
            candidate_queryset.values_list(
                "pk",
                flat=True,
            )
        )

        if not candidate_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    "No completed entries require backfill."
                )
            )
            return

        candidates = list(
            candidate_queryset
        )

        self.stdout.write(
            f"Found {len(candidates)} completed "
            "entries without playthrough history."
        )

        for entry in candidates:
            access = (
                entry.owned_accesses[0]
                if entry.owned_accesses
                else None
            )

            if access is None:
                access_label = (
                    "No Owned access · access will remain empty"
                )
            else:
                platform_label = (
                    access.get_platform_name_display()
                )

                store_label = (
                    access.get_store_display()
                    if access.store
                    else "No store"
                )

                access_label = (
                    f"{platform_label} · {store_label}"
                )

            prefix = (
                "[DRY RUN]"
                if dry_run
                else "[PENDING]"
            )

            self.stdout.write(
                f"{prefix} {entry.game.title} "
                f"→ Playthrough 1 · Completed "
                f"· Unspecified · {access_label}"
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run complete. "
                    "No database records were created."
                )
            )
            return

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            locked_entries = (
                LibraryEntry.objects
                .select_for_update()
                .select_related(
                    "game",
                )
                .filter(
                    pk__in=candidate_ids,
                )
                .prefetch_related(
                    Prefetch(
                        "accesses",
                        queryset=owned_accesses,
                        to_attr="owned_accesses",
                    )
                )
                .order_by(
                    "game__title",
                )
            )

            for entry in locked_entries:
                # Recheck inside the transaction so the command
                # remains safe when executed more than once.
                if entry.playthroughs.exists():
                    skipped_count += 1
                    continue

                access = (
                    entry.owned_accesses[0]
                    if entry.owned_accesses
                    else None
                )

                playthrough = Playthrough(
                    library_entry=entry,
                    access=access,
                    number=1,
                    status=Playthrough.Status.COMPLETED,
                    text_language=(
                        Playthrough
                        .TextLanguage
                        .UNSPECIFIED
                    ),
                )

                playthrough.full_clean()
                playthrough.save()

                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {entry.game.title} "
                        "→ Playthrough 1"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete. Created: {created_count}. "
                f"Skipped: {skipped_count}."
            )
        )