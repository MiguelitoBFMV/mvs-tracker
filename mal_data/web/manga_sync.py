from time import perf_counter

from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import redirect
from django.views.decorators.http import (
    require_POST,
)

from mal_data.services.manga_list_sync import (
    sync_all_manga_statuses,
)
from mal_data.services.manga_reading_sync import (
    sync_reading_progress,
)
from mal_data.services.manual_tracked_manga_sync import (
    sync_all_manual_tracked_manga,
)

@login_required
@require_POST
def sync_manga_library_view(request):
    started_at = perf_counter()

    try:
        results = sync_all_manga_statuses()

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

        elapsed_seconds = (
            perf_counter() - started_at
        )

        messages.success(
            request,
            (
                "Manga library synchronized from MAL. "
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
            (
                "Manga Library sync failed: "
                f"{error}"
            ),
        )

    return redirect(
        "manga_insights:dashboard"
    )


@login_required
@require_POST
def sync_reading_progress_view(request):
    started_at = perf_counter()

    try:
        results = sync_reading_progress()
        personal_results = results["personal"]

        changed_count = sum(
            1
            for result in personal_results
            if result["changed"]
        )

        error_results = [
            result
            for result in personal_results
            if not result["ok"]
        ]

        error_count = len(error_results)

        elapsed_seconds = (
            perf_counter() - started_at
        )

        message = (
            "Reading progress synchronized "
            "from MAL. "
            f"MAL Reading: "
            f"{results['list_checked']} · "
            f"Manual rescues: "
            f"{results['manual_checked']} · "
            f"Reconciled: "
            f"{results['reconciled_checked']} · "
            f"Changes: {changed_count} · "
            f"Active: "
            f"{results['active_after']} · "
            f"Errors: {error_count} · "
            f"Time: {elapsed_seconds:.1f}s"
        )

        if error_results:
            first_error = error_results[0]

            message += (
                " · First error: "
                f"{first_error['title']}: "
                f"{first_error['error']}"
            )

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
                "Reading Progress sync "
                f"failed: {error}"
            ),
        )

    return redirect(
        "manga_insights:dashboard"
    )


@login_required
@require_POST
def sync_manual_manga_rescues_view(request):
    started_at = perf_counter()

    try:
        results = (
            sync_all_manual_tracked_manga()
        )

        total_count = len(results)

        success_count = sum(
            1
            for result in results
            if result["ok"]
        )

        error_count = (
            total_count - success_count
        )

        reconstructed_count = sum(
            1
            for result in results
            if (
                result["ok"]
                and result["created"]
            )
        )

        refreshed_count = (
            success_count
            - reconstructed_count
        )

        elapsed_seconds = (
            perf_counter() - started_at
        )

        message = (
            "Manual manga rescues "
            "synchronized. "
            f"Checked: {total_count} · "
            f"Refreshed: {refreshed_count} · "
            f"Reconstructed: "
            f"{reconstructed_count} · "
            f"Errors: {error_count} · "
            f"Time: {elapsed_seconds:.1f}s"
        )

        if error_count:
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
                "Manual Manga Rescue sync "
                f"failed: {error}"
            ),
        )

    return redirect(
        "manga_insights:dashboard"
    )


