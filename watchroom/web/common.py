from django.db.models import (
    Exists,
    OuterRef,
    Prefetch,
)

from watchroom.models import (
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)


ACTIVE_RUN_STATUSES = (
    ViewingRun.Status.WATCHING,
    ViewingRun.Status.PAUSED,
)


def entry_queryset():
    progress_queryset = (
        SeasonProgress.objects
        .select_related("season")
        .order_by(
            "season__season_number",
            "pk",
        )
    )

    run_queryset = (
        ViewingRun.objects
        .prefetch_related(
            Prefetch(
                "season_progress",
                queryset=progress_queryset,
                to_attr="prefetched_progress",
            ),
        )
        .order_by(
            "-number",
            "-pk",
        )
    )

    season_queryset = (
        Season.objects
        .order_by(
            "season_number",
            "pk",
        )
    )

    active_rewatch = (
        ViewingRun.objects
        .filter(
            watch_entry=OuterRef("pk"),
            number__gt=1,
            status__in=ACTIVE_RUN_STATUSES,
        )
    )

    return (
        WatchEntry.objects
        .select_related("media_work")
        .prefetch_related(
            Prefetch(
                "viewing_runs",
                queryset=run_queryset,
                to_attr="prefetched_runs",
            ),
            Prefetch(
                "media_work__seasons",
                queryset=season_queryset,
                to_attr="prefetched_seasons",
            ),
        )
        .annotate(
            has_active_rewatch=Exists(
                active_rewatch
            ),
        )
    )


def decorate_run(run, seasons):
    progress_records = list(
        getattr(
            run,
            "prefetched_progress",
            [],
        )
    )

    run.progress_records = progress_records
    run.progress_by_season = {
        progress.season_id: progress
        for progress in progress_records
    }

    regular_season_ids = {
        season.pk
        for season in seasons
        if not season.is_special
    }

    regular_progress = [
        progress
        for progress in progress_records
        if progress.season_id
        in regular_season_ids
    ]

    run.episodes_watched_total = sum(
        progress.episodes_watched
        for progress in regular_progress
    )
    run.episode_total = sum(
        season.episode_count
        for season in seasons
        if not season.is_special
    )

    if run.episode_total:
        run.progress_summary = (
            f"{run.episodes_watched_total} / "
            f"{run.episode_total} episodes"
        )
    else:
        run.progress_summary = ""

    return run


def decorate_entry(entry):
    runs = list(
        getattr(
            entry,
            "prefetched_runs",
            [],
        )
    )
    seasons = list(
        getattr(
            entry.media_work,
            "prefetched_seasons",
            [],
        )
    )

    for run in runs:
        decorate_run(
            run,
            seasons,
        )

    entry.run_count = len(runs)

    entry.current_run = next(
        (
            run
            for run in runs
            if run.status
            in ACTIVE_RUN_STATUSES
        ),
        None,
    )

    entry.display_run = (
        entry.current_run
        or (
            runs[0]
            if runs
            else None
        )
    )

    entry.activity_label = (
        entry.get_status_display()
    )
    entry.progress_label = ""
    entry.overall_progress_label = ""
    entry.is_up_to_date = False

    if entry.current_run is not None:
        if entry.current_run.is_rewatch:
            if (
                entry.current_run.status
                == ViewingRun.Status.PAUSED
            ):
                entry.activity_label = (
                    "Rewatch Paused"
                )
            else:
                entry.activity_label = (
                    "Rewatching"
                )
        else:
            entry.activity_label = (
                entry.current_run
                .get_status_display()
            )

    if (
        entry.media_work.media_type
        == MediaWork.MediaType.MOVIE
    ):
        display_run = entry.display_run

        if (
            display_run is not None
            and display_run.progress_minutes
            is not None
        ):
            runtime = (
                entry.media_work
                .runtime_minutes
            )

            if runtime is not None:
                entry.progress_label = (
                    f"{display_run.progress_minutes}"
                    f" / {runtime} min"
                )
            else:
                entry.progress_label = (
                    f"{display_run.progress_minutes}"
                    " min watched"
                )
        elif (
            entry.media_work.runtime_minutes
            is not None
        ):
            entry.progress_label = (
                f"{entry.media_work.runtime_minutes}"
                " min runtime"
            )

        return entry

    display_run = entry.display_run

    if display_run is None:
        return entry

    entry.overall_progress_label = (
        display_run.progress_summary
    )

    progress_records = [
        progress
        for progress
        in display_run.progress_records
        if not progress.season.is_special
    ]

    if progress_records:
        current_progress = max(
            progress_records,
            key=lambda progress: (
                progress.season.season_number,
                progress.pk,
            ),
        )

        entry.progress_label = (
            f"Season "
            f"{current_progress.season.season_number}"
            f" · "
            f"{current_progress.episodes_watched}"
            f" / "
            f"{current_progress.season.episode_count}"
        )
    elif display_run.episode_total:
        entry.progress_label = (
            f"0 / "
            f"{display_run.episode_total} episodes"
        )

    entry.is_up_to_date = (
        entry.current_run is not None
        and display_run.episode_total > 0
        and (
            display_run.episodes_watched_total
            == display_run.episode_total
        )
    )

    return entry

