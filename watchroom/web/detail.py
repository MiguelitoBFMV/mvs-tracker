from django.shortcuts import (
    get_object_or_404,
    render,
)

from .common import (
    decorate_entry,
    entry_queryset,
)


def detail(request, slug):
    entry = get_object_or_404(
        entry_queryset(),
        media_work__slug=slug,
    )

    decorate_entry(entry)

    seasons = list(
        getattr(
            entry.media_work,
            "prefetched_seasons",
            [],
        )
    )

    progress_by_season = {}

    if entry.current_run is not None:
        progress_by_season = (
            entry.current_run
            .progress_by_season
        )

    for season in seasons:
        season.current_progress = (
            progress_by_season.get(
                season.pk
            )
        )

    regular_seasons = [
        season
        for season in seasons
        if not season.is_special
    ]
    special_seasons = [
        season
        for season in seasons
        if season.is_special
    ]

    context = {
        "active_page": "library",
        "entry": entry,
        "work": entry.media_work,
        "viewing_runs": (
            entry.prefetched_runs
        ),
        "regular_seasons": (
            regular_seasons
        ),
        "special_seasons": (
            special_seasons
        ),
    }

    return render(
        request,
        "watchroom/detail.html",
        context,
    )

