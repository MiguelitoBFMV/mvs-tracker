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


