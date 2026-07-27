from django.db.models import Count, Q, Sum
from django.shortcuts import render

from mal_data.models import MangaEntry


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

    context = {
        **metrics,
        "last_synced_entry": (
            manga_entries
            .order_by("-last_synced_at")
            .first()
        ),
    }

    return render(
        request,
        "mal_data/manga_dashboard.html",
        context,
    )


