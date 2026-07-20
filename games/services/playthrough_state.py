from django.db import transaction
from django.utils import timezone
from django.db.models import Max

from games.models import (
    GameAccess,
    LibraryEntry,
    Playthrough,
)


TRANSITIONS = {
    "pause": {
        Playthrough.Status.PLAYING:
            Playthrough.Status.PAUSED,
    },
    "resume": {
        Playthrough.Status.PAUSED:
            Playthrough.Status.PLAYING,
    },
    "complete": {
        Playthrough.Status.PLAYING:
            Playthrough.Status.COMPLETED,
        Playthrough.Status.PAUSED:
            Playthrough.Status.COMPLETED,
    },
    "drop": {
        Playthrough.Status.PLAYING:
            Playthrough.Status.DROPPED,
        Playthrough.Status.PAUSED:
            Playthrough.Status.DROPPED,
    },
}


def _synchronize_library_status(
    library_entry,
    fallback_status,
):
    statuses = library_entry.playthroughs.values_list(
        "status",
        flat=True,
    )

    if Playthrough.Status.PLAYING in statuses:
        library_entry.status = (
            LibraryEntry.Status.PLAYING
        )
    elif Playthrough.Status.PAUSED in statuses:
        library_entry.status = (
            LibraryEntry.Status.PAUSED
        )
    else:
        library_entry.status = fallback_status

    library_entry.full_clean()
    library_entry.save()


@transaction.atomic
def change_playthrough_state(
    *,
    playthrough,
    action,
):
    library_entry = playthrough.library_entry

    if (
        library_entry.status
        == LibraryEntry.Status.MULTIPLAYER
    ):
        raise ValueError(
            "Multiplayer entries do not use playthrough actions."
        )

    transition = TRANSITIONS.get(action, {})
    target_status = transition.get(
        playthrough.status
    )

    if target_status is None:
        raise ValueError(
            "This playthrough action is not available "
            "for its current state."
        )

    if action == "resume":
        (
            Playthrough.objects
            .filter(
                library_entry=library_entry,
                status=Playthrough.Status.PLAYING,
            )
            .exclude(pk=playthrough.pk)
            .update(
                status=Playthrough.Status.PAUSED,
            )
        )

        if playthrough.started_on is None:
            playthrough.started_on = (
                timezone.localdate()
            )

    if (
        action == "complete"
        and playthrough.finished_on is None
    ):
        playthrough.finished_on = (
            timezone.localdate()
        )

    playthrough.status = target_status
    playthrough.full_clean()
    playthrough.save()

    status_map = {
        Playthrough.Status.PLAYING:
            LibraryEntry.Status.PLAYING,
        Playthrough.Status.PAUSED:
            LibraryEntry.Status.PAUSED,
        Playthrough.Status.COMPLETED:
            LibraryEntry.Status.COMPLETED,
        Playthrough.Status.DROPPED:
            LibraryEntry.Status.DROPPED,
    }

    _synchronize_library_status(
        library_entry,
        status_map[target_status],
    )

    return playthrough

@transaction.atomic
def start_new_playthrough(
    *,
    library_entry,
    access,
    text_language,
    progress_note="",
    started_on=None,
    notes="",
):
    locked_entry = (
        LibraryEntry.objects
        .select_for_update()
        .get(pk=library_entry.pk)
    )

    if (
        locked_entry.status
        == LibraryEntry.Status.MULTIPLAYER
    ):
        raise ValueError(
            (
                "Persistent multiplayer games "
                "do not use playthroughs."
            )
        )

    if (
        access.library_entry_id
        != locked_entry.pk
        or access.access_type
        != GameAccess.AccessType.OWNED
    ):
        raise ValueError(
            (
                "The selected access does not belong "
                "to this library entry."
            )
        )

    (
        Playthrough.objects
        .filter(
            library_entry=locked_entry,
            status=Playthrough.Status.PLAYING,
        )
        .update(
            status=Playthrough.Status.PAUSED,
        )
    )

    highest_number = (
        Playthrough.objects
        .filter(library_entry=locked_entry)
        .aggregate(
            highest=Max("number")
        )["highest"]
        or 0
    )

    playthrough = Playthrough(
        library_entry=locked_entry,
        access=access,
        number=highest_number + 1,
        status=Playthrough.Status.PLAYING,
        text_language=text_language,
        progress_note=progress_note,
        started_on=(
            started_on or timezone.localdate()
        ),
        notes=notes,
    )

    playthrough.full_clean()
    playthrough.save()

    locked_entry.status = LibraryEntry.Status.PLAYING
    locked_entry.full_clean()
    locked_entry.save()

    return playthrough