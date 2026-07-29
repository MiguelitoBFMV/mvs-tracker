from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from mal_data.models import MangaSourceLink
from mal_data.services.manga_source_matching import (
    source_title_score,
)
from mal_data.services.manga_sources.registry import (
    build_provider_client,
    is_official_provider,
)


@dataclass(frozen=True)
class RankedMangaSourceCandidate:
    position: int
    score: Decimal
    source_id: str
    title: str
    url: str
    thumbnail_url: str | None = None


@dataclass(frozen=True)
class MangaSourceSearchResult:
    provider: str
    query: str
    score_query: str
    candidates: tuple[
        RankedMangaSourceCandidate,
        ...,
    ]


def resolve_source_query(
    manga,
    *,
    query="",
):
    resolved_query = (
        str(query).strip()
        or manga.title_english
        or manga.title
        or manga.title_japanese
        or ""
    )

    if not resolved_query:
        raise ValueError(
            "The manga has no searchable title."
        )

    return resolved_query


def resolve_score_query(
    manga,
    query,
):
    direct_lookup = (
        query.isdigit()
        or query.startswith(
            (
                "http://",
                "https://",
            )
        )
    )

    if not direct_lookup:
        return query

    return (
        manga.title_english
        or manga.title
        or manga.title_japanese
        or query
    )


def search_manga_sources(
    manga,
    *,
    provider,
    query="",
    limit=10,
):
    resolved_query = resolve_source_query(
        manga,
        query=query,
    )

    score_query = resolve_score_query(
        manga,
        resolved_query,
    )

    client = build_provider_client(
        provider
    )

    candidates = client.search(
        resolved_query
    )

    ranked_values = sorted(
        (
            (
                source_title_score(
                    score_query,
                    candidate.title,
                ),
                candidate,
            )
            for candidate in candidates
        ),
        key=lambda result: (
            -result[0],
            result[1].title.casefold(),
        ),
    )

    ranked_candidates = tuple(
        RankedMangaSourceCandidate(
            position=position,
            score=Decimal(
                f"{score:.2f}"
            ),
            source_id=candidate.source_id,
            title=candidate.title,
            url=candidate.url,
            thumbnail_url=(
                candidate.thumbnail_url
                or None
            ),
        )
        for position, (
            score,
            candidate,
        ) in enumerate(
            ranked_values[
                : max(int(limit), 1)
            ],
            start=1,
        )
    )

    return MangaSourceSearchResult(
        provider=provider,
        query=resolved_query,
        score_query=score_query,
        candidates=ranked_candidates,
    )


def get_candidate_by_position(
    search_result,
    position,
):
    if position < 1:
        raise ValueError(
            "Candidate position must be "
            "1 or greater."
        )

    for candidate in (
        search_result.candidates
    ):
        if candidate.position == position:
            return candidate

    raise ValueError(
        (
            "Cannot select result "
            f"{position}. Only "
            f"{len(search_result.candidates)} "
            "candidate(s) were returned."
        )
    )


def get_candidate_by_source_id(
    search_result,
    source_id,
):
    clean_source_id = str(
        source_id
    ).strip()

    for candidate in (
        search_result.candidates
    ):
        if (
            candidate.source_id
            == clean_source_id
        ):
            return candidate

    raise ValueError(
        (
            "The selected source candidate "
            "is no longer available."
        )
    )


def save_manga_source_candidate(
    manga,
    *,
    provider,
    candidate,
    search_query,
    priority=None,
):
    if (
        priority is not None
        and priority < 1
    ):
        raise ValueError(
            "Source priority must be "
            "1 or greater."
        )

    source_defaults = {
        "source_id": candidate.source_id,
        "source_title": candidate.title,
        "source_url": candidate.url,
        "thumbnail_url": (
            candidate.thumbnail_url
            or ""
        ),
        "match_score": candidate.score,
        "search_query": search_query,
        "active": True,
        "is_official": (
            is_official_provider(
                provider
            )
        ),
    }

    if priority is not None:
        source_defaults[
            "priority"
        ] = priority

    return (
        MangaSourceLink.objects
        .update_or_create(
            manga=manga,
            provider=provider,
            defaults=source_defaults,
        )
    )


@transaction.atomic
def save_manga_source_candidate_with_role(
    manga,
    *,
    provider,
    candidate,
    search_query,
    role,
):
    if role not in {
        "primary",
        "fallback",
    }:
        raise ValueError(
            "Source role must be primary "
            "or fallback."
        )

    existing_links = list(
        MangaSourceLink.objects
        .select_for_update()
        .filter(manga=manga)
        .exclude(provider=provider)
        .order_by(
            "priority",
            "provider",
        )
    )

    if role == "primary":
        temporary_priority = 1
    else:
        temporary_priority = (
            len(existing_links) + 1
        )

    source_link, created = (
        save_manga_source_candidate(
            manga,
            provider=provider,
            candidate=candidate,
            search_query=search_query,
            priority=temporary_priority,
        )
    )

    if role == "primary":
        ordered_links = [
            source_link,
            *existing_links,
        ]
    else:
        ordered_links = [
            *existing_links,
            source_link,
        ]

    changed_links = []

    for priority, link in enumerate(
        ordered_links,
        start=1,
    ):
        if link.priority == priority:
            continue

        link.priority = priority
        changed_links.append(link)

    if changed_links:
        MangaSourceLink.objects.bulk_update(
            changed_links,
            ["priority"],
        )

    source_link.refresh_from_db()

    return source_link, created

