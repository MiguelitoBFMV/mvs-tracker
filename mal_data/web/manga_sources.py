from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import (
    require_GET,
    require_POST,
)

from mal_data.models import (
    MangaEntry,
    MangaSourceLink,
)
from mal_data.services.manga_source_search import (
    get_candidate_by_source_id,
    save_manga_source_candidate_with_role,
    search_manga_sources,
)
from mal_data.services.manga_source_management import (
    make_manga_source_primary,
    toggle_manga_source_active,
    unlink_manga_source,
)
from mal_data.services.manga_source_signal_sync import (
    sync_external_chapter_signal,
)
from mal_data.services.manga_sources.registry import (
    PROVIDER_CLIENTS,
    get_provider_label,
)


def build_source_rows(manga):
    source_links = list(
        manga.source_links
        .all()
        .order_by(
            "priority",
            "provider",
        )
    )

    source_rows = []
    active_position = 0

    for source_link in source_links:
        role = None

        if source_link.active:
            active_position += 1

            role = (
                "primary"
                if active_position == 1
                else "fallback"
            )

        source_rows.append(
            {
                "link": source_link,
                "provider_label": (
                    get_provider_label(
                        source_link.provider
                    )
                ),
                "role": role,
            }
        )

    return source_rows


def build_provider_options():
    return [
        {
            "value": provider,
            "label": get_provider_label(
                provider
            ),
        }
        for provider in sorted(
            PROVIDER_CLIENTS
        )
    ]


def get_provider_search_help(
    provider,
):
    provider_help = {
        "manga_plus": (
            "MANGA Plus accepts a title "
            "ID or official title URL. "
            "Leaving the query empty uses "
            "the MAL title."
        ),
        "weeb_central": (
            "Weeb Central supports title "
            "search. Leaving the query "
            "empty uses the manga title "
            "stored from MAL."
        ),
    }

    return provider_help.get(
        provider,
        (
            "Leave the query empty to use "
            "the manga title stored from "
            "MAL."
        ),
    )


@login_required
@require_GET
def manga_source_management(
    request,
    mal_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    source_rows = build_source_rows(
        manga
    )

    selected_provider = (
        request.GET.get(
            "provider",
            "manga_plus",
        )
        .strip()
    )

    if (
        selected_provider
        not in PROVIDER_CLIENTS
    ):
        selected_provider = (
            "manga_plus"
            if "manga_plus"
            in PROVIDER_CLIENTS
            else sorted(
                PROVIDER_CLIENTS
            )[0]
        )

    source_query = request.GET.get(
        "query",
        "",
    ).strip()

    search_requested = (
        request.GET.get("search")
        == "1"
    )

    search_result = None
    search_error = ""

    if search_requested:
        try:
            search_result = (
                search_manga_sources(
                    manga,
                    provider=(
                        selected_provider
                    ),
                    query=source_query,
                    limit=10,
                )
            )

        except Exception as error:
            search_error = str(error)

    context = {
        "manga": manga,
        "source_rows": source_rows,
        "source_count": len(
            source_rows
        ),
        "provider_options": (
            build_provider_options()
        ),
        "selected_provider": (
            selected_provider
        ),
        "source_query": source_query,
        "search_requested": (
            search_requested
        ),
        "search_result": (
            search_result
        ),
        "search_error": search_error,
        "provider_help": (
            get_provider_search_help(
                selected_provider
            )
        ),
    }

    return render(
        request,
        "mal_data/manga_sources.html",
        context,
    )


@login_required
@require_POST
def save_manga_source(
    request,
    mal_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    provider = request.POST.get(
        "provider",
        "",
    ).strip()

    query = request.POST.get(
        "query",
        "",
    ).strip()

    source_id = request.POST.get(
        "source_id",
        "",
    ).strip()

    role = request.POST.get(
        "role",
        "",
    ).strip()

    management_url = reverse(
        (
            "manga_insights:"
            "manga_source_management"
        ),
        kwargs={
            "mal_id": manga.mal_id,
        },
    )

    search_parameters = urlencode(
        {
            "search": "1",
            "provider": provider,
            "query": query,
        }
    )

    redirect_url = (
        f"{management_url}?"
        f"{search_parameters}"
    )

    if provider not in PROVIDER_CLIENTS:
        messages.error(
            request,
            "Unsupported manga provider.",
        )
        return redirect(management_url)

    if not source_id:
        messages.error(
            request,
            (
                "No source candidate "
                "was selected."
            ),
        )
        return redirect(redirect_url)

    if role not in {
        "primary",
        "fallback",
    }:
        messages.error(
            request,
            "Invalid source role.",
        )
        return redirect(redirect_url)

    try:
        search_result = (
            search_manga_sources(
                manga,
                provider=provider,
                query=query,
                limit=32,
            )
        )

        candidate = (
            get_candidate_by_source_id(
                search_result,
                source_id,
            )
        )

        source_link, created = (
            save_manga_source_candidate_with_role(
                manga,
                provider=provider,
                candidate=candidate,
                search_query=(
                    search_result.query
                ),
                role=role,
            )
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Manga source could not "
                f"be saved: {error}"
            ),
        )
        return redirect(redirect_url)

    action = (
        "linked"
        if created
        else "updated"
    )

    role_label = (
        "Primary"
        if role == "primary"
        else "Fallback"
    )

    messages.success(
        request,
        (
            f"{get_provider_label(provider)} "
            f"{action} as {role_label}. "
            f"Source: "
            f"{source_link.source_title}."
        ),
    )

    return redirect(management_url)


@login_required
@require_POST
def make_manga_source_primary_view(
    request,
    mal_id,
    link_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    source_link = get_object_or_404(
        MangaSourceLink,
        pk=link_id,
        manga=manga,
    )

    try:
        source_link = (
            make_manga_source_primary(
                source_link
            )
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Source priority could not "
                f"be updated: {error}"
            ),
        )

    else:
        messages.success(
            request,
            (
                f"{get_provider_label(
                    source_link.provider
                )} is now the primary "
                "source."
            ),
        )

    return redirect(
        "manga_insights:"
        "manga_source_management",
        mal_id=manga.mal_id,
    )


@login_required
@require_POST
def toggle_manga_source_active_view(
    request,
    mal_id,
    link_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    source_link = get_object_or_404(
        MangaSourceLink,
        pk=link_id,
        manga=manga,
    )

    try:
        source_link = (
            toggle_manga_source_active(
                source_link
            )
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Source state could not "
                f"be updated: {error}"
            ),
        )

    else:
        state_label = (
            "activated"
            if source_link.active
            else "deactivated"
        )

        messages.success(
            request,
            (
                f"{get_provider_label(
                    source_link.provider
                )} was {state_label}."
            ),
        )

    return redirect(
        "manga_insights:"
        "manga_source_management",
        mal_id=manga.mal_id,
    )


@login_required
@require_POST
def unlink_manga_source_view(
    request,
    mal_id,
    link_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    source_link = get_object_or_404(
        MangaSourceLink,
        pk=link_id,
        manga=manga,
    )

    provider_label = get_provider_label(
        source_link.provider
    )

    try:
        result = unlink_manga_source(
            source_link
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Manga source could not "
                f"be unlinked: {error}"
            ),
        )

    else:
        messages.success(
            request,
            (
                f"{provider_label} was "
                "unlinked. Source: "
                f"{result['source_title']}."
            ),
        )

    return redirect(
        "manga_insights:"
        "manga_source_management",
        mal_id=manga.mal_id,
    )


@login_required
@require_POST
def sync_manga_source_now_view(
    request,
    mal_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    try:
        result = (
            sync_external_chapter_signal(
                manga
            )
        )

    except Exception as error:
        messages.error(
            request,
            (
                "External chapter signal "
                f"sync failed: {error}"
            ),
        )

    else:
        latest_chapter = result[
            "latest_chapter"
        ]

        if latest_chapter is None:
            messages.warning(
                request,
                (
                    "No usable chapters were "
                    "found. The Chapter Signal "
                    "was not modified."
                ),
            )

        else:
            source_link = result[
                "source_link"
            ]
            signal = result["signal"]

            fallback_label = (
                " · Fallback used"
                if result.get(
                    "used_fallback",
                    False,
                )
                else ""
            )

            messages.success(
                request,
                (
                    "Chapter Signal "
                    "synchronized. "
                    f"Source: "
                    f"{get_provider_label(
                        source_link.provider
                    )} · "
                    f"Latest: "
                    f"{latest_chapter.number} · "
                    f"Pending: "
                    f"{signal.pending_chapters}"
                    f"{fallback_label}"
                ),
            )

    return redirect(
        "manga_insights:"
        "manga_source_management",
        mal_id=manga.mal_id,
    )


