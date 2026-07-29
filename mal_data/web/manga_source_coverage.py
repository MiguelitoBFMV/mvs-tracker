from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import render
from django.views.decorators.http import (
    require_GET,
)

from mal_data.services.manga_source_coverage import (
    COVERAGE_LABELS,
    build_manga_source_coverage,
)


ALLOWED_COVERAGE_FILTERS = {
    "all",
    *COVERAGE_LABELS,
}


@login_required
@require_GET
def manga_source_coverage(request):
    selected_coverage = (
        request.GET.get(
            "coverage",
            "all",
        )
        .strip()
    )

    if (
        selected_coverage
        not in ALLOWED_COVERAGE_FILTERS
    ):
        selected_coverage = "all"

    coverage = (
        build_manga_source_coverage()
    )

    rows = coverage["rows"]

    if selected_coverage != "all":
        rows = [
            row
            for row in rows
            if (
                row["coverage_state"]
                == selected_coverage
            )
        ]

    filter_options = [
        {
            "value": "all",
            "label": "All",
        },
        *[
            {
                "value": value,
                "label": label,
            }
            for value, label in (
                COVERAGE_LABELS.items()
            )
        ],
    ]

    context = {
        "summary": coverage["summary"],
        "coverage_rows": rows,
        "selected_coverage": (
            selected_coverage
        ),
        "filter_options": (
            filter_options
        ),
    }

    return render(
        request,
        (
            "mal_data/"
            "manga_source_coverage.html"
        ),
        context,
    )