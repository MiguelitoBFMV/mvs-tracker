from time import perf_counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from mal_data.services.anime_list_sync import (
    sync_all_anime_statuses,
)
from mal_data.services.episode_signal_sync import (
    sync_episode_signals_complete,
)
from mal_data.services.manual_tracked_sync import (
    sync_manual_tracked_anime_entries,
)


def _failed_titles(results, limit=3):
    titles = [
        result["title"]
        for result in results
        if not result["ok"]
    ]

    return ", ".join(titles[:limit])


@login_required
@require_POST
def sync_mal_library_view(request):

    started_at = perf_counter()

    try:
        results = sync_all_anime_statuses(
            save_raw=False,
        )

        total_entries = sum(
            result["total"]
            for result in results
        )

        created_entries = sum(
            result["created"]
            for result in results
        )

        updated_entries = sum(
            result["updated"]
            for result in results
        )

        unchanged_entries = sum(
            result["unchanged"]
            for result in results
        )

        elapsed_seconds = perf_counter() - started_at

        messages.success(
            request,
            (
                "MAL Library synchronized. "
                f"Total: {total_entries} · "
                f"Created: {created_entries} · "
                f"Updated: {updated_entries} · "
                f"Unchanged: {unchanged_entries} · "
                f"Time: {elapsed_seconds:.1f}s"
            ),
        )

    except Exception as error:
        messages.error(
            request,
            f"MAL Library sync failed: {error}",
        )

    return redirect("mal_insights:dashboard")


@login_required
@require_POST
def sync_episode_signals_view(request):
    try:
        results = sync_episode_signals_complete()

        personal_results = results["personal"]
        airing_results = results["airing"]

        personal_ok = sum(
            1
            for result in personal_results
            if result["ok"]
        )

        personal_changed = sum(
            1
            for result in personal_results
            if (
                result["ok"]
                and result.get("changed")
            )
        )

        personal_errors = sum(
            1
            for result in personal_results
            if not result["ok"]
        )

        airing_ok = sum(
            1
            for result in airing_results
            if result["ok"]
        )

        airing_errors = sum(
            1
            for result in airing_results
            if not result["ok"]
        )

        total_errors = (
            personal_errors
            + airing_errors
        )

        message = (
            "Episode Signals synchronized. "
            f"MAL checked: {personal_ok} · "
            f"Progress changes: "
            f"{personal_changed} · "
            f"AniList updated: {airing_ok} · "
            f"Errors: {total_errors}"
        )

        if total_errors:
            messages.warning(
                request,
                message,
            )
        else:
            messages.success(
                request,
                message,
            )

    except Exception as error:
        messages.error(
            request,
            (
                "Episode Signals sync failed: "
                f"{error}"
            ),
        )

    return redirect("mal_insights:dashboard")


@login_required
@require_POST
def sync_manual_rescues_view(request):
    try:
        results = sync_manual_tracked_anime_entries()

        ok_count = sum(
            1
            for result in results
            if result["ok"]
        )

        error_count = sum(
            1
            for result in results
            if not result["ok"]
        )

        if error_count:
            failed_titles = _failed_titles(results)

            messages.warning(
                request,
                (
                    "Manual Rescues completed with errors. "
                    f"Updated: {ok_count} · "
                    f"Errors: {error_count} · "
                    f"Failed: {failed_titles}"
                ),
            )

        else:
            messages.success(
                request,
                (
                    "Manual Rescues synchronized. "
                    f"Active rescues updated: {ok_count}"
                ),
            )

    except Exception as error:
        messages.error(
            request,
            f"Manual Rescues sync failed: {error}",
        )

    return redirect("mal_insights:dashboard")
