from django.db import transaction
from django.utils import timezone

from mal_data.models import MangaSourceLink


def _compact_priorities(links):
    changed_links = []
    updated_at = timezone.now()

    for priority, source_link in enumerate(
        links,
        start=1,
    ):
        if source_link.priority == priority:
            continue

        source_link.priority = priority
        source_link.updated_at = updated_at
        changed_links.append(source_link)

    if changed_links:
        MangaSourceLink.objects.bulk_update(
            changed_links,
            [
                "priority",
                "updated_at",
            ],
        )


@transaction.atomic
def make_manga_source_primary(
    source_link,
):
    locked_links = list(
        MangaSourceLink.objects
        .select_for_update()
        .filter(
            manga=source_link.manga,
        )
        .order_by(
            "priority",
            "provider",
            "pk",
        )
    )

    locked_source = next(
        (
            link
            for link in locked_links
            if link.pk == source_link.pk
        ),
        None,
    )

    if locked_source is None:
        raise ValueError(
            "The manga source link no "
            "longer exists."
        )

    ordered_links = [
        locked_source,
        *[
            link
            for link in locked_links
            if link.pk != locked_source.pk
        ],
    ]

    updated_at = timezone.now()
    changed_links = []

    for priority, link in enumerate(
        ordered_links,
        start=1,
    ):
        changed = False

        if link.priority != priority:
            link.priority = priority
            changed = True

        if (
            link.pk == locked_source.pk
            and not link.active
        ):
            link.active = True
            changed = True

        if changed:
            link.updated_at = updated_at
            changed_links.append(link)

    if changed_links:
        MangaSourceLink.objects.bulk_update(
            changed_links,
            [
                "priority",
                "active",
                "updated_at",
            ],
        )

    locked_source.refresh_from_db()

    return locked_source


@transaction.atomic
def toggle_manga_source_active(
    source_link,
):
    locked_source = (
        MangaSourceLink.objects
        .select_for_update()
        .get(
            pk=source_link.pk,
            manga=source_link.manga,
        )
    )

    locked_source.active = (
        not locked_source.active
    )

    locked_source.save(
        update_fields=[
            "active",
            "updated_at",
        ]
    )

    return locked_source


@transaction.atomic
def unlink_manga_source(
    source_link,
):
    manga = source_link.manga

    locked_source = (
        MangaSourceLink.objects
        .select_for_update()
        .get(
            pk=source_link.pk,
            manga=manga,
        )
    )

    provider = locked_source.provider
    source_title = (
        locked_source.source_title
    )

    locked_source.delete()

    remaining_links = list(
        MangaSourceLink.objects
        .select_for_update()
        .filter(manga=manga)
        .order_by(
            "priority",
            "provider",
            "pk",
        )
    )

    _compact_priorities(
        remaining_links
    )

    return {
        "provider": provider,
        "source_title": source_title,
    }


