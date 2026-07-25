from django.db.models import (
    Count,
    Prefetch,
    Q,
)
from django.shortcuts import render

from watchroom.models import (
    MediaWork,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)


ACTIVE_RUN_STATUSES = (
    ViewingRun.Status.WATCHING,
    ViewingRun.Status.PAUSED,
)


def _dashboard_entries():
    progress_queryset = (
        SeasonProgress.objects
        .select_related("season")
        .order_by(
            "season__season_number",
            "pk",
        )
    )

    run_queryset = (
        ViewingRun.objects
        .prefetch_related(
            Prefetch(
                "season_progress",
                queryset=progress_queryset,
                to_attr=(
                    "dashboard_season_progress"
                ),
            ),
        )
        .order_by(
            "-number",
            "-pk",
        )
    )

    return (
        WatchEntry.objects
        .select_related("media_work")
        .prefetch_related(
            Prefetch(
                "viewing_runs",
                queryset=run_queryset,
                to_attr="dashboard_runs",
            ),
        )
    )


def _decorate_entry(entry):
    active_run = next(
        (
            run
            for run in entry.dashboard_runs
            if run.status
            in ACTIVE_RUN_STATUSES
        ),
        None,
    )

    entry.current_run = active_run
    entry.activity_label = (
        entry.get_status_display()
    )
    entry.progress_label = ""

    if active_run is None:
        return entry

    if active_run.is_rewatch:
        if (
            active_run.status
            == ViewingRun.Status.PAUSED
        ):
            entry.activity_label = (
                "Rewatch Paused"
            )
        else:
            entry.activity_label = (
                "Rewatching"
            )

    if (
        entry.media_work.media_type
        == MediaWork.MediaType.MOVIE
    ):
        if (
            active_run.progress_minutes
            is not None
        ):
            entry.progress_label = (
                f"{active_run.progress_minutes} "
                "minutes watched"
            )

        return entry

    progress_records = [
        progress
        for progress
        in active_run.dashboard_season_progress
        if not progress.season.is_special
    ]

    if not progress_records:
        entry.progress_label = (
            "No season progress yet"
        )
        return entry

    current_progress = max(
        progress_records,
        key=lambda progress: (
            progress.season.season_number,
            progress.pk,
        ),
    )

    entry.progress_label = (
        f"Season "
        f"{current_progress.season.season_number}"
        f" · "
        f"{current_progress.episodes_watched}"
        f" / "
        f"{current_progress.season.episode_count}"
    )

    return entry


def dashboard(request):
    entries = _dashboard_entries()

    counts = WatchEntry.objects.aggregate(
        total=Count("pk"),
        movies=Count(
            "pk",
            filter=Q(
                media_work__media_type=(
                    MediaWork.MediaType.MOVIE
                ),
            ),
        ),
        series=Count(
            "pk",
            filter=Q(
                media_work__media_type=(
                    MediaWork.MediaType.SERIES
                ),
            ),
        ),
        watching=Count(
            "pk",
            filter=Q(
                status=(
                    WatchEntry.Status.WATCHING
                ),
            ),
        ),
        completed=Count(
            "pk",
            filter=Q(
                status=(
                    WatchEntry.Status.COMPLETED
                ),
            ),
        ),
        plan_to_watch=Count(
            "pk",
            filter=Q(
                status=(
                    WatchEntry.Status
                    .PLAN_TO_WATCH
                ),
            ),
        ),
    )

    active_entries = list(
        entries
        .filter(
            status__in=(
                WatchEntry.Status.WATCHING,
                WatchEntry.Status.PAUSED,
                WatchEntry.Status.COMPLETED,
            ),
            viewing_runs__status__in=(
                ACTIVE_RUN_STATUSES
            ),
        )
        .distinct()
        .order_by(
            "-updated_at",
            "media_work__title",
        )[:6]
    )

    recent_entries = list(
        entries.order_by(
            "-updated_at",
            "media_work__title",
        )[:8]
    )

    for entry in active_entries:
        _decorate_entry(entry)

    for entry in recent_entries:
        _decorate_entry(entry)

    context = {
        "active_page": "dashboard",
        "active_entries": active_entries,
        "recent_entries": recent_entries,
        "total_count": counts["total"],
        "movie_count": counts["movies"],
        "series_count": counts["series"],
        "watching_count": counts[
            "watching"
        ],
        "completed_count": counts[
            "completed"
        ],
        "plan_to_watch_count": counts[
            "plan_to_watch"
        ],
    }

    return render(
        request,
        "watchroom/dashboard.html",
        context,
    )


