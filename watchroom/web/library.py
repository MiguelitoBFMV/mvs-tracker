from django.db.models import (
    F,
    Q,
)
from django.shortcuts import render

from watchroom.models import (
    MediaWork,
    WatchEntry,
)

from .common import (
    decorate_entry,
    entry_queryset,
)


ORDER_CHOICES = (
    ("title", "Title"),
    ("recent", "Recently Updated"),
    ("release_newest", "Newest Release"),
    ("release_oldest", "Oldest Release"),
)


def library(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()
    media_type = request.GET.get(
        "type",
        "",
    ).strip()
    status = request.GET.get(
        "status",
        "",
    ).strip()
    presentation = request.GET.get(
        "presentation",
        "",
    ).strip()
    activity = request.GET.get(
        "activity",
        "",
    ).strip()
    order = request.GET.get(
        "order",
        "title",
    ).strip()

    entries = entry_queryset()

    if query:
        entries = entries.filter(
            Q(
                media_work__title__icontains=(
                    query
                ),
            )
            | Q(
                media_work__original_title__icontains=(
                    query
                ),
            )
        )

    valid_types = {
        value
        for value, _label
        in MediaWork.MediaType.choices
    }

    if media_type in valid_types:
        entries = entries.filter(
            media_work__media_type=(
                media_type
            ),
        )

    valid_statuses = {
        value
        for value, _label
        in WatchEntry.Status.choices
    }

    if status in valid_statuses:
        entries = entries.filter(
            status=status,
        )

    valid_presentations = {
        value
        for value, _label
        in MediaWork.Presentation.choices
    }

    if presentation in valid_presentations:
        entries = entries.filter(
            media_work__presentation=(
                presentation
            ),
        )

    if activity == "rewatching":
        entries = entries.filter(
            has_active_rewatch=True,
        )

    valid_orders = {
        value
        for value, _label
        in ORDER_CHOICES
    }

    if order not in valid_orders:
        order = "title"

    if order == "recent":
        entries = entries.order_by(
            "-updated_at",
            "media_work__title",
        )
    elif order == "release_newest":
        entries = entries.order_by(
            F(
                "media_work__first_release_date"
            ).desc(
                nulls_last=True,
            ),
            "media_work__title",
        )
    elif order == "release_oldest":
        entries = entries.order_by(
            F(
                "media_work__first_release_date"
            ).asc(
                nulls_last=True,
            ),
            "media_work__title",
        )
    else:
        entries = entries.order_by(
            "media_work__title",
        )

    entries = entries.distinct()
    result_count = entries.count()
    entries = list(entries)

    for entry in entries:
        decorate_entry(entry)

    context = {
        "active_page": "library",
        "entries": entries,
        "result_count": result_count,
        "query": query,
        "selected_type": media_type,
        "selected_status": status,
        "selected_presentation": (
            presentation
        ),
        "selected_activity": activity,
        "selected_order": order,
        "type_choices": (
            MediaWork.MediaType.choices
        ),
        "status_choices": (
            WatchEntry.Status.choices
        ),
        "presentation_choices": (
            MediaWork.Presentation.choices
        ),
        "order_choices": ORDER_CHOICES,
    }

    return render(
        request,
        "watchroom/library.html",
        context,
    )


