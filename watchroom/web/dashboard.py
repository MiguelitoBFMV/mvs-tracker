from django.db.models import (
    Count,
    Q,
)
from django.shortcuts import render

from watchroom.models import (
    MediaWork,
    WatchEntry,
)

from .common import (
    ACTIVE_RUN_STATUSES,
    decorate_entry,
    entry_queryset,
)


def dashboard(request):
    entries = entry_queryset()

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
        entries
        .order_by(
            "-updated_at",
            "media_work__title",
        )[:8]
    )

    for entry in active_entries:
        decorate_entry(entry)

    for entry in recent_entries:
        decorate_entry(entry)

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


