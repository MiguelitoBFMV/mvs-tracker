from mal_data.models import (
    MangaSourceLink,
)
from mal_data.services.manga_sources.registry import (
    build_provider_client,
)


class MangaSourceLinkNotFoundError(
    ValueError
):
    pass


class MangaSourceFetchError(
    RuntimeError
):
    pass


def get_saved_source_links(
    manga,
    *,
    provider=None,
):
    source_links = (
        MangaSourceLink.objects
        .filter(
            manga=manga,
            active=True,
        )
        .order_by(
            "priority",
            "provider",
        )
    )

    if provider:
        source_links = (
            source_links.filter(
                provider=provider,
            )
        )

    source_links = list(source_links)

    if not source_links:
        if provider:
            message = (
                "No active saved source "
                f"exists for {manga.title} "
                f"using provider "
                f"{provider}."
            )

        else:
            message = (
                "No active saved manga "
                f"source exists for "
                f"{manga.title}."
            )

        raise MangaSourceLinkNotFoundError(
            message
        )

    return source_links


def get_saved_source_link(
    manga,
    *,
    provider=None,
):
    return get_saved_source_links(
        manga,
        provider=provider,
    )[0]


def fetch_latest_saved_chapter(
    manga,
    *,
    provider=None,
):
    source_links = get_saved_source_links(
        manga,
        provider=provider,
    )

    attempts = []
    first_empty_source = None

    for source_link in source_links:
        try:
            client = build_provider_client(
                source_link.provider
            )

            latest_chapter = (
                client.fetch_latest_chapter(
                    source_link.source_url
                )
            )

        except Exception as error:
            attempts.append(
                {
                    "provider": (
                        source_link.provider
                    ),
                    "priority": (
                        source_link.priority
                    ),
                    "status": "error",
                    "ok": False,
                    "error": str(error),
                }
            )

            continue

        if latest_chapter is None:
            if first_empty_source is None:
                first_empty_source = (
                    source_link
                )

            attempts.append(
                {
                    "provider": (
                        source_link.provider
                    ),
                    "priority": (
                        source_link.priority
                    ),
                    "status": "empty",
                    "ok": True,
                    "error": None,
                }
            )

            continue

        attempts.append(
            {
                "provider": (
                    source_link.provider
                ),
                "priority": (
                    source_link.priority
                ),
                "status": "success",
                "ok": True,
                "error": None,
            }
        )

        return (
            source_link,
            latest_chapter,
            attempts,
        )

    if first_empty_source is not None:
        return (
            first_empty_source,
            None,
            attempts,
        )

    attempt_details = "; ".join(
        (
            f"{attempt['provider']}: "
            f"{attempt['error']}"
        )
        for attempt in attempts
    )

    raise MangaSourceFetchError(
        (
            "All active manga sources "
            f"failed for {manga.title}. "
            f"{attempt_details}"
        )
    )

