from datetime import (
    datetime,
    timedelta,
    timezone as datetime_timezone,
)

from django.db.models import Q, Max
from django.utils import timezone
from django.utils.dateparse import (
    parse_datetime,
)

from mal_data.models import (
    MangaChapterSignal,
    MangaEntry,
    MangaSyncEvent
)

RECENT_READING_WINDOW_DAYS = 14

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


def build_chapter_release_display(
    signal,
    *,
    reference_time,
):
    published_at = (
        get_signal_published_at(
            signal
        )
    )

    if published_at is not None:
        event_time = published_at
        label_prefix = "Latest Chapter"

    elif (
        signal.latest_available_changed_at
        is not None
    ):
        event_time = (
            signal
            .latest_available_changed_at
        )
        label_prefix = "Detected"

    else:
        return None

    event_time = timezone.localtime(
        event_time
    )

    reference_time = timezone.localtime(
        reference_time
    )

    age = (
        reference_time
        - event_time
    )

    seconds = max(
        int(age.total_seconds()),
        0,
    )

    if seconds < 60:
        value = "just now"

    elif seconds < 3600:
        minutes = seconds // 60

        value = (
            f"{minutes} min ago"
        )

    elif seconds < 86400:
        hours = seconds // 3600

        value = (
            f"{hours}h ago"
        )

    elif seconds < 604800:
        days = seconds // 86400

        value = (
            f"{days}d ago"
        )

    elif (
        event_time.year
        == reference_time.year
    ):
        value = event_time.strftime(
            "%b %d"
        )

    else:
        value = event_time.strftime(
            "%b %d, %Y"
        )

    return {
        "prefix": label_prefix,
        "value": value,
        "datetime": event_time,
    }


def chapter_signal_priority(
    signal,
    *,
    reference_time,
    last_chapter_activity=None,
):
    manga = signal.manga

    available_changed_at = (
        signal.latest_available_changed_at
    )

    published_at = (
        get_signal_published_at(
            signal
        )
    )

    changed_sort = (
        available_changed_at.timestamp()
        if available_changed_at
        else 0
    )

    published_sort = (
        published_at.timestamp()
        if published_at
        else 0
    )

    pending = float(
        signal.pending_chapters
    )

    title = (
        manga.title
        or ""
    ).casefold()

    # 1. CAPÍTULO NUEVO
    #
    # La disponibilidad cambió después
    # de nuestra última actualización
    # personal de capítulos.
    has_new_release = (
        available_changed_at
        is not None
        and (
            last_chapter_activity
            is None
            or available_changed_at
            > last_chapter_activity
        )
    )

    if has_new_release:
        return (
            0,
            -changed_sort,
            -published_sort,
            title,
        )

    # 2. LECTURA RECIENTE
    #
    # Solo usamos CH_UPDATE real.
    # Ya no updated_at_mal.
    recent_cutoff = (
        reference_time
        - timedelta(days=14)
    )

    has_recent_activity = (
        last_chapter_activity
        is not None
        and last_chapter_activity
        >= recent_cutoff
    )

    if has_recent_activity:
        return (
            1,
            -last_chapter_activity.timestamp(),
            pending,
            title,
        )

    # 3. BACKLOG
    #
    # Finished y Publishing compiten
    # por capítulos pendientes.
    #
    # Menos pendientes = más arriba.
    if manga.publication_status in {
        "finished",
        "currently_publishing",
    }:
        publication_rank = (
            0
            if manga.publication_status
            == "finished"
            else 1
        )

        return (
            2,
            pending,
            publication_rank,
            -published_sort,
            title,
        )

    # 4. RESTO
    return (
        3,
        pending,
        title,
    )


def get_actionable_chapter_signals(
    *,
    limit=None,
):
    signals = (
        MangaChapterSignal.objects
        .select_related("manga")
        .filter(
            Q(
                manga__list_status="reading"
            )
            | Q(
                manga__is_rereading=True
            )
        )
    )

    actionable = [
        signal
        for signal in signals
        if signal.has_signal
    ]

    if not actionable:
        return []

    mal_ids = [
        signal.mal_id
        for signal in actionable
    ]

    chapter_activity_rows = (
        MangaSyncEvent.objects
        .filter(
            event_type="chapter_changed",
            mal_id__in=mal_ids,
        )
        .values(
            "mal_id"
        )
        .annotate(
            last_chapter_activity=Max(
                "created_at"
            )
        )
    )

    chapter_activity_by_mal_id = {
        row["mal_id"]: (
            row[
                "last_chapter_activity"
            ]
        )
        for row in chapter_activity_rows
    }

    reference_time = timezone.now()

    actionable = sorted(
        actionable,
        key=lambda signal: (
            chapter_signal_priority(
                signal,
                reference_time=(
                    reference_time
                ),
                last_chapter_activity=(
                    chapter_activity_by_mal_id
                    .get(
                        signal.mal_id
                    )
                ),
            )
        ),
    )

    for signal in actionable:
        signal.release_display = (
            build_chapter_release_display(
                signal,
                reference_time=(
                    reference_time
                ),
            )
        )

    if limit is not None:
        return actionable[:limit]

    return actionable

