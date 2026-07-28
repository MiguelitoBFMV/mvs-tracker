from django.db.models import Count, Q, Sum
from django.shortcuts import render

from mal_data.models import (
    MangaEntry,
    MangaSyncEvent,
)
from mal_data.services.manga_chapter_signal_sync import (
    get_actionable_chapter_signals,
)


def manga_dashboard(request):
    manga_entries = MangaEntry.objects.all()

    metrics = manga_entries.aggregate(
        total_manga=Count("id"),
        reading_count=Count(
            "id",
            filter=Q(list_status="reading"),
        ),
        rereading_count=Count(
            "id",
            filter=Q(is_rereading=True),
        ),
        completed_count=Count(
            "id",
            filter=Q(list_status="completed"),
        ),
        plan_to_read_count=Count(
            "id",
            filter=Q(list_status="plan_to_read"),
        ),
        on_hold_count=Count(
            "id",
            filter=Q(list_status="on_hold"),
        ),
        dropped_count=Count(
            "id",
            filter=Q(list_status="dropped"),
        ),
        chapters_read=Sum("num_chapters_read"),
        volumes_read=Sum("num_volumes_read"),
    )

    metrics["chapters_read"] = (
        metrics["chapters_read"] or 0
    )
    metrics["volumes_read"] = (
        metrics["volumes_read"] or 0
    )

    chapter_signal_entries = (
        get_actionable_chapter_signals(
            limit=15
        )
    )

    backlog_total = (
        metrics["completed_count"]
        + metrics["plan_to_read_count"]
    )

    if backlog_total > 0:
        backlog_clear_ratio = round(
            metrics["completed_count"]
            / backlog_total
            * 100
        )
    else:
        backlog_clear_ratio = 0

    spotlight_manga = (
        manga_entries
        .filter(
            Q(list_status="reading")
            | Q(is_rereading=True)
        )
        .exclude(
            title_japanese__isnull=True
        )
        .exclude(
            title_japanese=""
        )
        .order_by(
            "-score",
            "-updated_at_mal",
            "title",
        )
        .first()
    )

    latest_sync_events = (
        MangaSyncEvent.objects
        .select_related("manga")
        .order_by("-created_at")[:15]
    )

    last_synced_entry = (
        manga_entries
        .order_by("-last_synced_at")
        .first()
    )

    context = {
        **metrics,
        "chapter_signal_entries": (
            chapter_signal_entries
        ),
        "backlog_clear_ratio": (
            backlog_clear_ratio
        ),
        "spotlight_manga": spotlight_manga,
        "latest_sync_events": (
            latest_sync_events
        ),
        "last_synced_entry": (
            last_synced_entry
        ),
    }

    return render(
        request,
        "mal_data/manga_dashboard.html",
        context,
    )

