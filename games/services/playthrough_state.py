from django.db import transaction
from django.utils import timezone

from games.models import LibraryEntry, Playthrough


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