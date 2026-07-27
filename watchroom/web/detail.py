from django.shortcuts import (
    get_object_or_404,
    render,
)

from watchroom.forms import (
    NewViewingRunOwnerForm,
    SeasonOwnerForm,
    SeasonProgressOwnerForm,
    ViewingRunOwnerForm,
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
    new_run_form=None,
    run_update_form=None,
    run_action_error=None,
    run_action_id=None,
    progress_update_form=None,
    progress_run_id=None,
    progress_season_id=None,
):
    decorate_entry(entry)

    seasons = list(
        getattr(
            entry.media_work,
            "prefetched_seasons",
            [],
        )
    )
    viewing_runs = list(
        getattr(
            entry,
            "prefetched_runs",
            [],
        )
    )

    display_progress_run = (
        entry.current_run
        or entry.display_run
    )

    owner_progress_run = (
        entry.current_run
    )

    progress_by_season = {}

    if display_progress_run is not None:
        progress_by_season = (
            display_progress_run
            .progress_by_season
        )

    for season in seasons:
        season.current_progress = (
            progress_by_season.get(
                season.pk
            )
        )
        season.owner_form = None
        season.progress_form = None

    for run in viewing_runs:
        run.owner_form = None

    if request.user.is_authenticated:
        if entry_form is None:
            entry_form = WatchEntryOwnerForm(
                instance=entry,
                prefix="entry",
            )

        if new_run_form is None:
            new_run_form = (
                NewViewingRunOwnerForm(
                    watch_entry=entry,
                    prefix="new-run",
                )
            )

        for run in viewing_runs:
            if (
                run_update_form is not None
                and run.pk
                == run_update_form.instance.pk
            ):
                run.owner_form = (
                    run_update_form
                )
            else:
                run.owner_form = (
                    ViewingRunOwnerForm(
                        instance=run,
                        watch_entry=entry,
                        prefix=(
                            f"run-{run.pk}"
                        ),
                    )
                )

        if (
            entry.media_work.media_type
            == entry.media_work.MediaType.SERIES
        ):
            if new_season_form is None:
                new_season_form = (
                    SeasonOwnerForm(
                        media_work=(
                            entry.media_work
                        ),
                        prefix="new-season",
                    )
                )

            for season in seasons:
                if (
                    season_update_form is not None
                    and season.pk
                    == (
                        season_update_form
                        .instance
                        .pk
                    )
                ):
                    season.owner_form = (
                        season_update_form
                    )
                else:
                    season.owner_form = (
                        SeasonOwnerForm(
                            instance=season,
                            media_work=(
                                entry.media_work
                            ),
                            prefix=(
                                f"season-"
                                f"{season.pk}"
                            ),
                        )
                    )

            if owner_progress_run is not None:
                for season in seasons:
                    existing_progress = (
                        owner_progress_run
                        .progress_by_season
                        .get(season.pk)
                    )

                    if (
                        progress_update_form
                        is not None
                        and progress_run_id
                        == owner_progress_run.pk
                        and progress_season_id
                        == season.pk
                    ):
                        season.progress_form = (
                            progress_update_form
                        )
                    else:
                        season.progress_form = (
                            SeasonProgressOwnerForm(
                                instance=(
                                    existing_progress
                                ),
                                viewing_run=(
                                    owner_progress_run
                                ),
                                season=season,
                                prefix=(
                                    f"progress-"
                                    f"{owner_progress_run.pk}-"
                                    f"{season.pk}"
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

    franchise_memberships = list(
        entry.media_work
        .franchise_memberships
        .select_related(
            "franchise"
        )
        .order_by(
            "franchise__name",
            "position",
            "pk",
        )
    )

    return {
        "active_page": "library",
        "entry": entry,
        "work": entry.media_work,
        "viewing_runs": viewing_runs,
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
        "new_run_form": new_run_form,
        "run_action_error": (
            run_action_error
        ),
        "run_action_id": (
            run_action_id
        ),
        "progress_run": owner_progress_run,
        "can_start_run": (
            entry.current_run is None
        ),
        "franchise_memberships": (
            franchise_memberships
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

