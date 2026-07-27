from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from mal_data.models import (
    ManualTrackedManga,
)
from mal_data.services.manual_tracked_manga_sync import (
    sync_manual_tracked_manga_entry,
)


VALID_STATUSES = (
    "reading",
    "completed",
    "on_hold",
    "dropped",
    "plan_to_read",
)


class Command(BaseCommand):
    help = (
        "Rescata uno o varios mangas que "
        "la lista general de MAL omite."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "mal_ids",
            nargs="+",
            type=int,
        )

        parser.add_argument(
            "--status",
            choices=VALID_STATUSES,
            required=True,
            help=(
                "Estado fallback cuando MAL "
                "no devuelve my_list_status."
            ),
        )

        parser.add_argument(
            "--chapters-read",
            type=int,
            default=0,
        )

        parser.add_argument(
            "--volumes-read",
            type=int,
            default=0,
        )

        parser.add_argument(
            "--score",
            type=int,
            default=0,
        )

        parser.add_argument(
            "--rereading",
            action="store_true",
        )

        parser.add_argument(
            "--notes",
            default="",
        )

    def handle(self, *args, **options):
        mal_ids = list(
            dict.fromkeys(
                options["mal_ids"]
            )
        )

        success_count = 0
        error_count = 0

        for mal_id in mal_ids:
            tracked_entry, tracker_created = (
                ManualTrackedManga
                .objects
                .update_or_create(
                    mal_id=mal_id,
                    defaults={
                        "status": (
                            options["status"]
                        ),
                        "chapters_read": (
                            options[
                                "chapters_read"
                            ]
                        ),
                        "volumes_read": (
                            options[
                                "volumes_read"
                            ]
                        ),
                        "score": (
                            options["score"]
                        ),
                        "is_rereading": (
                            options[
                                "rereading"
                            ]
                        ),
                        "active": True,
                        "notes": (
                            options["notes"]
                            or None
                        ),
                    },
                )
            )

            try:
                manga, manga_created = (
                    sync_manual_tracked_manga_entry(
                        tracked_entry
                    )
                )

            except Exception as error:
                error_count += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"{mal_id}: {error}"
                    )
                )
                continue

            success_count += 1

            tracker_action = (
                "created"
                if tracker_created
                else "updated"
            )

            manga_action = (
                "created"
                if manga_created
                else "updated"
            )

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{mal_id} · "
                        f"{manga.display_title} · "
                        f"{manga.list_status} · "
                        f"CH. "
                        f"{manga.num_chapters_read} · "
                        f"VOL. "
                        f"{manga.num_volumes_read} · "
                        f"tracker {tracker_action} · "
                        f"entry {manga_action}"
                    )
                )
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Rescue complete · "
                    f"OK: {success_count} · "
                    f"Errors: {error_count}"
                )
            )
        )

        if error_count:
            raise CommandError(
                (
                    f"{error_count} manga rescue "
                    "operation(s) failed."
                )
            )


    