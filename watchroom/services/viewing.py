from django.core.exceptions import (
    ValidationError,
)
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from watchroom.models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)


ACTIVE_RUN_STATUSES = (
    ViewingRun.Status.WATCHING,
    ViewingRun.Status.PAUSED,
)


def sync_entry_status(watch_entry):
    has_completed_run = (
        watch_entry.viewing_runs.filter(
            status=ViewingRun.Status.COMPLETED,
        ).exists()
    )

    active_run = (
        watch_entry.viewing_runs.filter(
            status__in=ACTIVE_RUN_STATUSES,
        )
        .order_by(
            "-number",
            "-pk",
        )
        .first()
    )

    if has_completed_run:
        new_status = (
            WatchEntry.Status.COMPLETED
        )
    elif active_run is not None:
        if (
            active_run.status
            == ViewingRun.Status.PAUSED
        ):
            new_status = (
                WatchEntry.Status.PAUSED
            )
        else:
            new_status = (
                WatchEntry.Status.WATCHING
            )
    elif watch_entry.viewing_runs.filter(
        status=ViewingRun.Status.DROPPED,
    ).exists():
        new_status = (
            WatchEntry.Status.DROPPED
        )
    else:
        new_status = (
            WatchEntry.Status.PLAN_TO_WATCH
        )

    if watch_entry.status != new_status:
        watch_entry.status = new_status

        watch_entry.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

    return new_status


@transaction.atomic
def create_viewing_run(
    *,
    watch_entry,
    started_on=None,
    progress_minutes=None,
    notes="",
):
    locked_entry = (
        WatchEntry.objects
        .select_for_update()
        .select_related("media_work")
        .get(pk=watch_entry.pk)
    )

    if locked_entry.viewing_runs.filter(
        status__in=ACTIVE_RUN_STATUSES,
    ).exists():
        raise ValidationError(
            (
                "This work already has an "
                "active or paused viewing run."
            )
        )

    highest_number = (
        locked_entry.viewing_runs
        .aggregate(
            highest=Max("number"),
        )["highest"]
        or 0
    )

    run = ViewingRun(
        watch_entry=locked_entry,
        number=highest_number + 1,
        status=ViewingRun.Status.WATCHING,
        started_on=started_on,
        progress_minutes=progress_minutes,
        notes=notes,
    )

    run.full_clean()
    run.save()

    sync_entry_status(locked_entry)

    return run


def series_run_has_full_progress(
    viewing_run,
):
    work = (
        viewing_run
        .watch_entry
        .media_work
    )

    if (
        work.media_type
        != MediaWork.MediaType.SERIES
    ):
        return False

    regular_seasons = list(
        Season.objects.filter(
            media_work=work,
            season_number__gt=0,
            episode_count__gt=0,
        ).values_list(
            "pk",
            "episode_count",
        )
    )

    if not regular_seasons:
        return False

    season_ids = [
        season_id
        for season_id, _episode_count
        in regular_seasons
    ]

    progress_by_season = dict(
        SeasonProgress.objects.filter(
            viewing_run=viewing_run,
            season_id__in=season_ids,
        ).values_list(
            "season_id",
            "episodes_watched",
        )
    )

    return all(
        progress_by_season.get(
            season_id,
            0,
        )
        >= episode_count
        for season_id, episode_count
        in regular_seasons
    )


def _validate_series_completion(run):
    work = run.watch_entry.media_work

    known_regular_seasons = list(
        Season.objects.filter(
            media_work=work,
            season_number__gt=0,
            episode_count__gt=0,
        ).order_by(
            "season_number",
            "pk",
        )
    )

    if not known_regular_seasons:
        raise ValidationError(
            (
                "This series has no known regular "
                "season episodes to complete."
            )
        )

    progress_by_season = {
        progress.season_id: (
            progress.episodes_watched
        )
        for progress
        in SeasonProgress.objects.filter(
            viewing_run=run,
            season__in=known_regular_seasons,
        )
    }

    has_incomplete_season = any(
        progress_by_season.get(
            season.pk,
            0,
        )
        < season.episode_count
        for season in known_regular_seasons
    )

    if has_incomplete_season:
        raise ValidationError(
            (
                "Complete all known regular "
                "seasons before completing "
                "this viewing run."
            )
        )


@transaction.atomic
def transition_viewing_run(
    *,
    viewing_run,
    action,
):
    run = (
        ViewingRun.objects
        .select_for_update()
        .select_related(
            "watch_entry",
            "watch_entry__media_work",
        )
        .get(pk=viewing_run.pk)
    )

    valid_actions = {
        "pause",
        "resume",
        "complete",
        "drop",
    }

    if action not in valid_actions:
        raise ValidationError(
            "Unknown viewing-run action."
        )

    if action == "pause":
        if (
            run.status
            != ViewingRun.Status.WATCHING
        ):
            raise ValidationError(
                (
                    "Only a watching run "
                    "can be paused."
                )
            )

        run.status = ViewingRun.Status.PAUSED
        run.finished_on = None

    elif action == "resume":
        if (
            run.status
            != ViewingRun.Status.PAUSED
        ):
            raise ValidationError(
                (
                    "Only a paused run "
                    "can be resumed."
                )
            )

        run.status = ViewingRun.Status.WATCHING
        run.finished_on = None

    elif action == "complete":
        if run.status not in {
            ViewingRun.Status.WATCHING,
            ViewingRun.Status.PAUSED,
        }:
            raise ValidationError(
                (
                    "Only an active or paused run "
                    "can be completed."
                )
            )

        if (
            run.watch_entry.media_work.media_type
            == MediaWork.MediaType.SERIES
        ):
            _validate_series_completion(run)

        run.status = ViewingRun.Status.COMPLETED

        if run.finished_on is None:
            run.finished_on = timezone.localdate()

        work = run.watch_entry.media_work

        if (
            work.media_type
            == MediaWork.MediaType.MOVIE
            and work.runtime_minutes is not None
        ):
            run.progress_minutes = (
                work.runtime_minutes
            )

    elif action == "drop":
        if run.status not in {
            ViewingRun.Status.WATCHING,
            ViewingRun.Status.PAUSED,
        }:
            raise ValidationError(
                (
                    "Only an active or paused run "
                    "can be dropped."
                )
            )

        run.status = ViewingRun.Status.DROPPED
        run.finished_on = None

    run.full_clean()

    run.save(
        update_fields=[
            "status",
            "finished_on",
            "progress_minutes",
            "updated_at",
        ],
    )

    sync_entry_status(
        run.watch_entry
    )

    return run


