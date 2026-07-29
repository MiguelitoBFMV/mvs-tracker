from datetime import (
    datetime,
    timezone as datetime_timezone,
)

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import (
    parse_datetime,
)

from mal_data.models import (
    MangaChapterSignal,
    MangaEntry,
)


def get_chapter_signal_targets():
    return (
        MangaEntry.objects
        .filter(
            Q(list_status="reading")
            | Q(is_rereading=True)
        )
        .order_by(
            "title",
            "mal_id",
        )
    )


def sync_canonical_chapter_signals():
    targets = list(
        get_chapter_signal_targets()
    )

    existing_by_mal_id = (
        MangaChapterSignal.objects.in_bulk(
            [
                manga.mal_id
                for manga in targets
            ],
            field_name="mal_id",
        )
    )

    sync_time = timezone.now()

    created_count = 0
    updated_count = 0
    unchanged_count = 0

    for manga in targets:
        canonical_total = (
            manga.num_chapters or 0
        )

        signal = existing_by_mal_id.get(
            manga.mal_id
        )

        if signal is None:
            MangaChapterSignal.objects.create(
                manga=manga,
                mal_id=manga.mal_id,
                canonical_total_chapters=(
                    canonical_total
                ),
                availability_source_type=(
                    "canonical"
                ),
                last_synced_at=sync_time,
            )

            created_count += 1
            continue

        changed_fields = []

        if signal.manga_id != manga.id:
            signal.manga = manga
            changed_fields.append("manga")

        if (
            signal.canonical_total_chapters
            != canonical_total
        ):
            signal.canonical_total_chapters = (
                canonical_total
            )
            changed_fields.append(
                "canonical_total_chapters"
            )

        signal.last_synced_at = sync_time

        if changed_fields:
            signal.save(
                update_fields=[
                    *changed_fields,
                    "last_synced_at",
                ]
            )
            updated_count += 1
        else:
            signal.save(
                update_fields=[
                    "last_synced_at",
                ]
            )
            unchanged_count += 1

    actionable_count = sum(
        1
        for signal in (
            MangaChapterSignal.objects
            .select_related("manga")
            .filter(
                Q(
                    manga__list_status=(
                        "reading"
                    )
                )
                | Q(
                    manga__is_rereading=True
                )
            )
        )
        if signal.has_signal
    )

    return {
        "targets": len(targets),
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "actionable": actionable_count,
    }


def get_signal_published_at(signal):
    external_source = (
        (signal.raw_data or {})
        .get(
            "external_source",
            {},
        )
    )

    raw_published_at = (
        external_source.get(
            "published_at"
        )
    )

    if not raw_published_at:
        return None

    if isinstance(
        raw_published_at,
        datetime,
    ):
        published_at = raw_published_at

    else:
        published_at = parse_datetime(
            str(raw_published_at)
        )

    if published_at is None:
        return None

    if timezone.is_naive(
        published_at
    ):
        published_at = (
            timezone.make_aware(
                published_at,
                datetime_timezone.utc,
            )
        )

    return published_at


def chapter_signal_priority(signal):
    manga = signal.manga

    # Esta jerarquía ya deja espacio para
    # las reglas siguientes:
    #
    # 0: publicación activa + fuente viva
    # 1: publicación activa
    # 2: relación con anime activo
    # 3: manga finalizado
    # 4: rereading
    if manga.is_rereading:
        group = 4

    elif (
        manga.publication_status
        == "currently_publishing"
        and signal.has_live_availability
    ):
        group = 0

    elif (
        manga.publication_status
        == "currently_publishing"
    ):
        group = 1

    elif (
        manga.publication_status
        == "finished"
    ):
        group = 3

    else:
        group = 2

    published_at = (
        get_signal_published_at(
            signal
        )
    )

    published_sort = (
        published_at.timestamp()
        if published_at
        else 0
    )

    return (
        group,
        -published_sort,
        -float(
            signal.pending_chapters
        ),
        manga.title.lower(),
    )


def get_actionable_chapter_signals(
    *,
    limit=None,
):
    signals = (
        MangaChapterSignal.objects
        .select_related("manga")
        .filter(
            Q(manga__list_status="reading")
            | Q(manga__is_rereading=True)
        )
    )

    actionable = [
        signal
        for signal in signals
        if signal.has_signal
    ]

    actionable = sorted(
        actionable,
        key=chapter_signal_priority,
    )

    if limit is not None:
        return actionable[:limit]

    return actionable

