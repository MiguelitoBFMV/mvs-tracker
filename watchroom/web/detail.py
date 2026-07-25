from django.shortcuts import (
    get_object_or_404,
    render,
)

from watchroom.forms import (
    SeasonOwnerForm,
    WatchEntryOwnerForm,
)

from .common import (
    decorate_entry,
    entry_queryset,
)


def _get_detail_entry(slug):
    return get_object_or_404(
        entry_queryset(),
        media_work__slug=slug,
    )


def _build_detail_context(
    request,
    entry,
    *,
    entry_form=None,
    new_season_form=None,
    season_update_form=None,
    season_action_error=None,
    season_action_id=None,
):
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
        season.owner_form = None

    if request.user.is_authenticated:
        if entry_form is None:
            entry_form = WatchEntryOwnerForm(
                instance=entry,
                prefix="entry",
            )

        if (
            entry.media_work.media_type
            == entry.media_work.MediaType.SERIES
            and new_season_form is None
        ):
            new_season_form = SeasonOwnerForm(
                media_work=entry.media_work,
                prefix="new-season",
            )

        for season in seasons:
            if (
                season_update_form is not None
                and season.pk
                == season_update_form.instance.pk
            ):
                season.owner_form = (
                    season_update_form
                )
            else:
                season.owner_form = (
                    SeasonOwnerForm(
                        instance=season,
                        media_work=entry.media_work,
                        prefix=(
                            f"season-{season.pk}"
                        ),
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

    return {
        "active_page": "library",
        "entry": entry,
        "work": entry.media_work,
        "viewing_runs": (
            entry.prefetched_runs
        ),
        "all_seasons": seasons,
        "regular_seasons": (
            regular_seasons
        ),
        "special_seasons": (
            special_seasons
        ),
        "entry_form": entry_form,
        "new_season_form": (
            new_season_form
        ),
        "season_action_error": (
            season_action_error
        ),
        "season_action_id": (
            season_action_id
        ),
    }


def render_detail(
    request,
    slug,
    **context_overrides,
):
    entry = _get_detail_entry(slug)

    return render(
        request,
        "watchroom/detail.html",
        _build_detail_context(
            request,
            entry,
            **context_overrides,
        ),
    )


def detail(request, slug):
    return render_detail(
        request,
        slug,
    )