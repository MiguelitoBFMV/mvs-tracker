from django.core.paginator import Paginator
from django.db.models import (
    Case,
    IntegerField,
    Q,
    Value,
    When,
)
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from mal_data.models import MangaEntry


VALID_MANGA_STATUSES = {
    "all": "All manga",
    "reading": "Reading",
    "completed": "Completed",
    "plan_to_read": "Plan to read",
    "on_hold": "On hold",
    "dropped": "Dropped",
}


STATUS_ORDER = [
    "reading",
    "completed",
    "plan_to_read",
    "on_hold",
    "dropped",
]


PUBLICATION_LABELS = {
    "currently_publishing": "Publishing",
    "finished": "Finished",
    "on_hiatus": "On Hiatus",
    "discontinued": "Discontinued",
}


MEDIA_TYPE_LABELS = {
    "manga": "Manga",
    "light_novel": "Light Novel",
    "manhwa": "Manhwa",
    "one_shot": "One-shot",
}


ALLOWED_SORTS = {
    "title": "title",
    "-title": "-title",
    "score": "score",
    "-score": "-score",
    "num_chapters_read": (
        "num_chapters_read"
    ),
    "-num_chapters_read": (
        "-num_chapters_read"
    ),
    "num_volumes_read": (
        "num_volumes_read"
    ),
    "-num_volumes_read": (
        "-num_volumes_read"
    ),
    "publication_status": (
        "publication_status"
    ),
    "-publication_status": (
        "-publication_status"
    ),
    "media_type": "media_type",
    "-media_type": "-media_type",
    "updated_at_mal": "updated_at_mal",
    "-updated_at_mal": (
        "-updated_at_mal"
    ),
}


def build_query_without(request, *keys):
    params = request.GET.copy()

    for key in keys:
        if key in params:
            del params[key]

    return params.urlencode()


def manga_status_list(request, status):
    if status not in VALID_MANGA_STATUSES:
        raise Http404(
            "Estado de manga no válido"
        )

    status_filter_options = [
        (
            status_key,
            VALID_MANGA_STATUSES[
                status_key
            ],
        )
        for status_key in STATUS_ORDER
    ]

    if status == "all":
        selected_statuses = (
            request.GET.getlist("statuses")
        )

        if not selected_statuses:
            selected_statuses = (
                STATUS_ORDER.copy()
            )

        selected_statuses = [
            selected_status
            for selected_status
            in selected_statuses
            if selected_status
            in STATUS_ORDER
        ]

        if not selected_statuses:
            selected_statuses = (
                STATUS_ORDER.copy()
            )

        if len(selected_statuses) == 1:
            target_status = (
                selected_statuses[0]
            )

            redirect_url = reverse(
                "manga_insights:"
                "manga_status_list",
                kwargs={
                    "status": target_status,
                },
            )

            remaining_query = (
                request.GET.copy()
            )

            if "statuses" in remaining_query:
                del remaining_query[
                    "statuses"
                ]

            query_string = (
                remaining_query.urlencode()
            )

            if query_string:
                redirect_url = (
                    f"{redirect_url}?"
                    f"{query_string}"
                )

            return redirect(redirect_url)

        status_query = Q()

        if "reading" in selected_statuses:
            status_query |= (
                Q(list_status="reading")
                | Q(is_rereading=True)
            )

        remaining_statuses = [
            selected_status
            for selected_status
            in selected_statuses
            if selected_status != "reading"
        ]

        if remaining_statuses:
            status_query |= Q(
                list_status__in=(
                    remaining_statuses
                )
            )

        manga_entries = (
            MangaEntry.objects.filter(
                status_query
            )
        )

    else:
        selected_statuses = [status]

        if status == "reading":
            manga_entries = (
                MangaEntry.objects.filter(
                    Q(list_status="reading")
                    | Q(is_rereading=True)
                )
            )
        else:
            manga_entries = (
                MangaEntry.objects.filter(
                    list_status=status
                )
            )

    publication_values = list(
        MangaEntry.objects
        .exclude(
            publication_status__isnull=True
        )
        .exclude(
            publication_status=""
        )
        .order_by("publication_status")
        .values_list(
            "publication_status",
            flat=True,
        )
        .distinct()
    )

    publication_options = [
        (
            value,
            PUBLICATION_LABELS.get(
                value,
                value,
            ),
        )
        for value in publication_values
    ]

    publication_filter = (
        request.GET.get("publication")
    )

    if publication_filter in (
        publication_values
    ):
        manga_entries = (
            manga_entries.filter(
                publication_status=(
                    publication_filter
                )
            )
        )
    else:
        publication_filter = None

    media_type_values = list(
        MangaEntry.objects
        .exclude(
            media_type__isnull=True
        )
        .exclude(
            media_type=""
        )
        .order_by("media_type")
        .values_list(
            "media_type",
            flat=True,
        )
        .distinct()
    )

    media_type_options = [
        (
            value,
            MEDIA_TYPE_LABELS.get(
                value,
                value,
            ),
        )
        for value in media_type_values
    ]

    media_type_filter = (
        request.GET.get("media_type")
    )

    if media_type_filter in (
        media_type_values
    ):
        manga_entries = (
            manga_entries.filter(
                media_type=media_type_filter
            )
        )
    else:
        media_type_filter = None

    sort = request.GET.get("sort")

    if sort in ALLOWED_SORTS:
        manga_entries = (
            manga_entries.order_by(
                ALLOWED_SORTS[sort]
            )
        )

    elif status == "all":
        sort = "status_priority"

        status_priority = Case(
            When(
                is_rereading=True,
                then=Value(0),
            ),
            When(
                list_status="reading",
                then=Value(0),
            ),
            When(
                list_status="completed",
                then=Value(1),
            ),
            When(
                list_status="plan_to_read",
                then=Value(2),
            ),
            When(
                list_status="on_hold",
                then=Value(3),
            ),
            When(
                list_status="dropped",
                then=Value(4),
            ),
            default=Value(99),
            output_field=IntegerField(),
        )

        manga_entries = (
            manga_entries.annotate(
                status_priority=(
                    status_priority
                )
            )
            .order_by(
                "status_priority",
                "-updated_at_mal",
                "title",
            )
        )

    elif status in {
        "plan_to_read",
        "on_hold",
    }:
        sort = "title"
        manga_entries = (
            manga_entries.order_by("title")
        )

    else:
        sort = "-updated_at_mal"
        manga_entries = (
            manga_entries.order_by(
                "-updated_at_mal",
                "title",
            )
        )

    paginator = Paginator(
        manga_entries,
        50,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "status": status,
        "status_label": (
            VALID_MANGA_STATUSES[status]
        ),
        "page_obj": page_obj,
        "manga_entries": (
            page_obj.object_list
        ),
        "total_entries": paginator.count,
        "sort": sort,
        "selected_statuses": (
            selected_statuses
        ),
        "status_filter_options": (
            status_filter_options
        ),
        "publication_filter": (
            publication_filter
        ),
        "publication_options": (
            publication_options
        ),
        "media_type_filter": (
            media_type_filter
        ),
        "media_type_options": (
            media_type_options
        ),
        "pagination_query": (
            build_query_without(
                request,
                "page",
            )
        ),
        "sort_query": (
            build_query_without(
                request,
                "page",
                "sort",
            )
        ),
    }

    return render(
        request,
        "mal_data/manga_status_list.html",
        context,
    )

