from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import (
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import (
    require_POST,
)

from mal_data.models import (
    MangaEntry,
    ManualTrackedManga,
)
from mal_data.services.anilist_client import (
    AniListClient,
)
from mal_data.services.manual_tracked_manga_sync import (
    sync_manual_tracked_manga_entry,
)


def manga_search_view(request):
    query = request.GET.get(
        "q",
        "",
    ).strip()

    results = []
    search_error = None

    if query:
        try:
            client = AniListClient()

            candidates = (
                client.search_manga_candidates(
                    query
                )
            )

            for candidate in candidates:
                mal_id = candidate.get(
                    "idMal"
                )

                local_entry = None
                manual_entry = None

                if mal_id:
                    local_entry = (
                        MangaEntry.objects
                        .filter(
                            mal_id=mal_id
                        )
                        .first()
                    )

                    manual_entry = (
                        ManualTrackedManga
                        .objects
                        .filter(
                            mal_id=mal_id
                        )
                        .first()
                    )

                cover = (
                    candidate.get(
                        "coverImage"
                    )
                    or {}
                )

                results.append(
                    {
                        "anilist_id": (
                            candidate.get(
                                "id"
                            )
                        ),
                        "mal_id": mal_id,
                        "title": (
                            candidate.get(
                                "title"
                            )
                            or {}
                        ),
                        "status": (
                            candidate.get(
                                "status"
                            )
                        ),
                        "format": (
                            candidate.get(
                                "format"
                            )
                        ),
                        "chapters": (
                            candidate.get(
                                "chapters"
                            )
                        ),
                        "volumes": (
                            candidate.get(
                                "volumes"
                            )
                        ),
                        "country": (
                            candidate.get(
                                "countryOfOrigin"
                            )
                        ),
                        "cover_url": (
                            cover.get(
                                "extraLarge"
                            )
                            or cover.get(
                                "large"
                            )
                            or cover.get(
                                "medium"
                            )
                        ),
                        "local_entry": (
                            local_entry
                        ),
                        "manual_entry": (
                            manual_entry
                        ),
                    }
                )

        except Exception as error:
            search_error = str(error)

    def search_result_priority(result):
        if result["local_entry"]:
            local_group = 0

        elif result["manual_entry"]:
            local_group = 1

        else:
            local_group = 2

        has_mal_id_group = (
            0
            if result["mal_id"]
            else 1
        )

        publishing_group = (
            0
            if result["status"]
            == "RELEASING"
            else 1
        )

        return (
            local_group,
            has_mal_id_group,
            publishing_group,
            (
                result["title"]
                .get("romaji")
                or ""
            ),
        )

    results = sorted(
        results,
        key=search_result_priority,
    )

    return render(
        request,
        "mal_data/manga_search.html",
        {
            "query": query,
            "results": results,
            "search_error": (
                search_error
            ),
        },
    )


def parse_non_negative_int(
    value,
    *,
    field_name,
    maximum=None,
):
    try:
        resolved = int(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"Invalid {field_name}."
        ) from error

    if resolved < 0:
        raise ValueError(
            f"{field_name} cannot be negative."
        )

    if (
        maximum is not None
        and resolved > maximum
    ):
        raise ValueError(
            (
                f"{field_name} cannot "
                f"exceed {maximum}."
            )
        )

    return resolved


@login_required
@require_POST
def rescue_manga_from_search_view(
    request,
):
    mal_id = request.POST.get(
        "mal_id"
    )

    title_snapshot = (
        request.POST.get(
            "title_snapshot",
            "",
        )
        .strip()
    )

    status = request.POST.get(
        "status",
        "reading",
    )

    return_query = (
        request.POST.get(
            "return_query",
            "",
        )
        .strip()
    )

    if not mal_id:
        messages.error(
            request,
            (
                "Cannot rescue manga "
                "without MAL ID."
            ),
        )

        return redirect(
            "manga_insights:manga_search"
        )

    valid_statuses = {
        value
        for value, _label in (
            ManualTrackedManga
            .STATUS_CHOICES
        )
    }

    if status not in valid_statuses:
        messages.error(
            request,
            "Invalid manga status.",
        )

        return redirect(
            "manga_insights:manga_search"
        )

    try:
        chapters_read = (
            parse_non_negative_int(
                request.POST.get(
                    "chapters_read"
                ),
                field_name=(
                    "chapters read"
                ),
            )
        )

        volumes_read = (
            parse_non_negative_int(
                request.POST.get(
                    "volumes_read"
                ),
                field_name=(
                    "volumes read"
                ),
            )
        )

        score = parse_non_negative_int(
            request.POST.get(
                "score"
            ),
            field_name="score",
            maximum=10,
        )

        tracked_entry, _ = (
            ManualTrackedManga.objects
            .update_or_create(
                mal_id=int(mal_id),
                defaults={
                    "title_snapshot": (
                        title_snapshot
                    ),
                    "status": status,
                    "chapters_read": (
                        chapters_read
                    ),
                    "volumes_read": (
                        volumes_read
                    ),
                    "score": score,
                    "is_rereading": False,
                    "active": True,
                },
            )
        )

        manga, created = (
            sync_manual_tracked_manga_entry(
                tracked_entry
            )
        )

        messages.success(
            request,
            (
                "Manga rescued and tracked. "
                f"Node: "
                f"{manga.display_title} · "
                f"Status: "
                f"{manga.personal_status_label} · "
                f"Created: {created}"
            ),
        )

    except Exception as error:
        messages.error(
            request,
            f"Rescue failed: {error}",
        )

    search_url = reverse(
        "manga_insights:manga_search"
    )

    if return_query:
        query_string = urlencode(
            {
                "q": return_query,
            }
        )

        return redirect(
            f"{search_url}?"
            f"{query_string}"
        )

    return redirect(search_url)

