from django.db.models import (
    Count,
    Prefetch,
    Q,
)

from mal_data.models import (
    MangaEntry,
    MangaSourceLink,
)
from mal_data.services.manga_sources.registry import (
    get_provider_label,
)


COVERAGE_LABELS = {
    "ready": "Ready",
    "single_source": "Single Source",
    "disabled": "Disabled",
    "needs_setup": "Needs Setup",
}

COVERAGE_ORDER = {
    "needs_setup": 0,
    "disabled": 1,
    "single_source": 2,
    "ready": 3,
}


def get_manga_source_coverage_targets():
    active_source_links = (
        MangaSourceLink.objects
        .filter(active=True)
        .order_by(
            "priority",
            "provider",
            "pk",
        )
    )

    return (
        MangaEntry.objects
        .filter(
            Q(list_status="reading")
            | Q(is_rereading=True),
            publication_status=(
                "currently_publishing"
            ),
        )
        .annotate(
            active_source_count=Count(
                "source_links",
                filter=Q(
                    source_links__active=True
                ),
                distinct=True,
            ),
            linked_source_count=Count(
                "source_links",
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "source_links",
                queryset=active_source_links,
                to_attr=(
                    "active_coverage_sources"
                ),
            )
        )
        .order_by(
            "title",
            "mal_id",
        )
    )


def classify_manga_source_coverage(
    *,
    active_count,
    linked_count,
):
    if active_count >= 2:
        return "ready"

    if active_count == 1:
        return "single_source"

    if linked_count > 0:
        return "disabled"

    return "needs_setup"


def build_manga_source_coverage():
    rows = []

    summary = {
        "targets": 0,
        "ready": 0,
        "single_source": 0,
        "disabled": 0,
        "needs_setup": 0,
    }

    for manga in (
        get_manga_source_coverage_targets()
    ):
        active_links = list(
            manga.active_coverage_sources
        )

        coverage_state = (
            classify_manga_source_coverage(
                active_count=(
                    manga.active_source_count
                ),
                linked_count=(
                    manga.linked_source_count
                ),
            )
        )

        active_sources = [
            {
                "link": source_link,
                "provider_label": (
                    get_provider_label(
                        source_link.provider
                    )
                ),
            }
            for source_link in active_links
        ]

        primary_source = (
            active_sources[0]
            if active_sources
            else None
        )

        rows.append(
            {
                "manga": manga,
                "coverage_state": (
                    coverage_state
                ),
                "coverage_label": (
                    COVERAGE_LABELS[
                        coverage_state
                    ]
                ),
                "active_source_count": (
                    manga.active_source_count
                ),
                "linked_source_count": (
                    manga.linked_source_count
                ),
                "active_sources": (
                    active_sources
                ),
                "primary_source": (
                    primary_source
                ),
            }
        )

        summary["targets"] += 1
        summary[coverage_state] += 1

    rows.sort(
        key=lambda row: (
            COVERAGE_ORDER[
                row["coverage_state"]
            ],
            row["manga"].title.casefold(),
            row["manga"].mal_id,
        )
    )

    return {
        "summary": summary,
        "rows": rows,
    }

