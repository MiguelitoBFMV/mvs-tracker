from django.db.models import Q
from django.utils import timezone

from mal_data.models import (
    MangaChapterSignal,
    MangaEntry,
)
from mal_data.services.manga_source_resolver import (
    fetch_latest_saved_chapter,
)
from mal_data.services.manga_sources.registry import (
    get_provider_label,
)


def sync_external_chapter_signal(
    manga,
    *,
    provider=None,
):
    (
        source_link,
        latest_chapter,
        attempts,
    ) = fetch_latest_saved_chapter(
        manga,
        provider=provider,
    )

    used_fallback = (
        latest_chapter is not None
        and len(attempts) > 1
    )

    if latest_chapter is None:
        return {
            "source_link": source_link,
            "latest_chapter": None,
            "signal": None,
            "created": False,
            "changed": False,
            "used_fallback": False,
            "attempts": attempts,
        }

    checked_at = timezone.now()

    signal, created = (
        MangaChapterSignal.objects
        .get_or_create(
            manga=manga,
            defaults={
                "mal_id": manga.mal_id,
            },
        )
    )

    previous_values = (
        signal.latest_available_chapter,
        signal.availability_source_type,
        signal.availability_source_name,
        signal.availability_source_url,
    )

    raw_data = dict(
        signal.raw_data or {}
    )

    raw_data["external_source"] = {
        "provider": source_link.provider,
        "source_id": source_link.source_id,
        "source_title": (
            source_link.source_title
        ),
        "source_url": (
            source_link.source_url
        ),
        "chapter_id": (
            latest_chapter.source_id
        ),
        "chapter_label": (
            latest_chapter.label
        ),
        "chapter_number": str(
            latest_chapter.number
        ),
        "chapter_url": (
            latest_chapter.url
        ),
        "published_at": (
            latest_chapter
            .published_at
            .isoformat()
            if latest_chapter.published_at
            else None
        ),
        "used_fallback": used_fallback,
        "attempts": attempts,
    }

    signal.mal_id = manga.mal_id
    signal.latest_available_chapter = (
        latest_chapter.number
    )
    signal.availability_source_type = (
        "external"
    )
    signal.availability_source_name = (
        get_provider_label(
            source_link.provider
        )
    )
    signal.availability_source_url = (
        source_link.source_url
    )
    signal.external_checked_at = (
        checked_at
    )
    signal.raw_data = raw_data
    signal.last_synced_at = checked_at

    current_values = (
        signal.latest_available_chapter,
        signal.availability_source_type,
        signal.availability_source_name,
        signal.availability_source_url,
    )

    changed = (
        created
        or previous_values
        != current_values
    )

    signal.save(
        update_fields=[
            "mal_id",
            "latest_available_chapter",
            "availability_source_type",
            "availability_source_name",
            "availability_source_url",
            "external_checked_at",
            "raw_data",
            "last_synced_at",
        ]
    )

    return {
        "source_link": source_link,
        "latest_chapter": latest_chapter,
        "signal": signal,
        "created": created,
        "changed": changed,
        "used_fallback": used_fallback,
        "attempts": attempts,
    }


def get_external_signal_targets():
    return (
        MangaEntry.objects
        .filter(
            Q(list_status="reading")
            | Q(is_rereading=True),
            source_links__active=True,
        )
        .distinct()
        .order_by(
            "title",
            "mal_id",
        )
    )


def sync_all_external_chapter_signals():
    targets = list(
        get_external_signal_targets()
    )

    created_count = 0
    updated_count = 0
    unchanged_count = 0
    empty_count = 0
    error_count = 0

    # NUEVO:
    # Cuenta cuántos mangas necesitaron
    # utilizar una fuente de respaldo.
    fallback_count = 0

    results = []

    for manga in targets:
        try:
            result = (
                sync_external_chapter_signal(
                    manga
                )
            )

        except Exception as error:
            error_count += 1

            results.append(
                {
                    "mal_id": manga.mal_id,
                    "title": manga.title,
                    "provider": None,
                    "status": "error",
                    "ok": False,
                    "error": str(error),

                    # NUEVO:
                    # Un error total no cuenta
                    # como fallback exitoso.
                    "used_fallback": False,
                }
            )

            # El error de un manga no detiene
            # la sincronización de los demás.
            continue

        source_link = result[
            "source_link"
        ]
        latest_chapter = result[
            "latest_chapter"
        ]

        # NUEVO:
        # sync_external_chapter_signal()
        # informa si tuvo que pasar desde
        # la fuente principal al respaldo.
        used_fallback = result.get(
            "used_fallback",
            False,
        )

        if used_fallback:
            fallback_count += 1

        if latest_chapter is None:
            empty_count += 1
            status = "empty"

        elif result["created"]:
            created_count += 1
            status = "created"

        elif result["changed"]:
            updated_count += 1
            status = "updated"

        else:
            unchanged_count += 1
            status = "unchanged"

        results.append(
            {
                "mal_id": manga.mal_id,
                "title": manga.title,
                "provider": (
                    source_link.provider
                ),
                "status": status,
                "ok": True,
                "error": None,

                # NUEVO:
                # Dejamos registrado el dato
                # para este manga concreto.
                "used_fallback": (
                    used_fallback
                ),
            }
        )

    return {
        "targets": len(targets),
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "empty": empty_count,
        "errors": error_count,

        # NUEVO:
        # Resumen total para el dashboard.
        "fallbacks": fallback_count,

        "results": results,
    }

