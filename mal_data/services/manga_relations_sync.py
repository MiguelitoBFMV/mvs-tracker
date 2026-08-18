import json

from datetime import datetime

from django.conf import settings
from django.utils import timezone

from mal_data.models import (
    AnimeEntry,
    AnimeMetadata,
    MangaEntry,
    MangaRelation,
)
from mal_data.services.anilist_client import (
    AniListClient,
)


def sync_manga_relations(
    manga_id,
    save_raw=True,
):
    client = AniListClient()

    data = (
        client
        .fetch_manga_relations_by_mal_id(
            manga_id
        )
    )

    if not data:
        raise ValueError(
            "AniList returned no manga "
            "for this MAL ID."
        )

    if save_raw:
        save_raw_json(
            manga_id,
            data,
        )

    source_mal_id = (
        data.get("idMal")
        or manga_id
    )

    source_title_data = (
        data.get("title")
        or {}
    )

    source_title = (
        source_title_data.get(
            "romaji"
        )
        or source_title_data.get(
            "english"
        )
        or source_title_data.get(
            "native"
        )
        or ""
    )

    source_manga = (
        MangaEntry.objects
        .filter(
            mal_id=source_mal_id
        )
        .first()
    )

    (
        related_anime,
        related_manga,
    ) = normalize_anilist_relations(
        data
    )

    prune_stale_relations(
        source_mal_id=source_mal_id,
        related_anime=related_anime,
        related_manga=related_manga,
    )

    (
        anime_created,
        anime_updated,
    ) = save_relations(
        source_manga=source_manga,
        source_mal_id=source_mal_id,
        source_title=source_title,
        items=related_anime,
        relation_source_type="anime",
    )

    (
        manga_created,
        manga_updated,
    ) = save_relations(
        source_manga=source_manga,
        source_mal_id=source_mal_id,
        source_title=source_title,
        items=related_manga,
        relation_source_type="manga",
    )

    return {
        "source_mal_id": (
            source_mal_id
        ),
        "source_title": (
            source_title
        ),
        "related_anime_count": (
            len(related_anime)
        ),
        "related_manga_count": (
            len(related_manga)
        ),
        "anime_created": (
            anime_created
        ),
        "anime_updated": (
            anime_updated
        ),
        "manga_created": (
            manga_created
        ),
        "manga_updated": (
            manga_updated
        ),
    }

ANILIST_RELATION_TYPES = {
    "ADAPTATION": (
        "adaptation",
        "Adaptation",
    ),
    "PREQUEL": (
        "prequel",
        "Prequel",
    ),
    "SEQUEL": (
        "sequel",
        "Sequel",
    ),
    "PARENT": (
        "parent_story",
        "Parent Story",
    ),
    "SIDE_STORY": (
        "side_story",
        "Side Story",
    ),
    "SPIN_OFF": (
        "spin_off",
        "Spin-Off",
    ),
    "ALTERNATIVE": (
        "alternative_version",
        "Alternative Version",
    ),
    "SUMMARY": (
        "summary",
        "Summary",
    ),
    "CHARACTER": (
        "character",
        "Character",
    ),
    "SOURCE": (
        "source",
        "Source",
    ),
    "COMPILATION": (
        "compilation",
        "Compilation",
    ),
    "CONTAINS": (
        "contains",
        "Contains",
    ),
    "OTHER": (
        "other",
        "Other",
    ),
}


def normalize_anilist_relations(
    data,
):
    related_anime = []
    related_manga = []

    relations = (
        data.get("relations")
        or {}
    )

    for edge in relations.get(
        "edges",
        [],
    ):
        node = (
            edge.get("node")
            or {}
        )

        target_mal_id = (
            node.get("idMal")
        )

        # Sin MAL ID no podemos vincularlo
        # al archivo canónico de MVS.
        if not target_mal_id:
            continue

        media_type = (
            node.get("type")
            or ""
        ).upper()

        if media_type not in {
            "ANIME",
            "MANGA",
        }:
            continue

        (
            relation_type,
            relation_label,
        ) = ANILIST_RELATION_TYPES.get(
            edge.get("relationType"),
            (
                "other",
                (
                    edge.get(
                        "relationType"
                    )
                    or "Other"
                )
                .replace("_", " ")
                .title()
            ),
        )

        normalized_node = (
            normalize_anilist_node(
                node
            )
        )

        item = {
            "node": normalized_node,
            "relation_type": (
                relation_type
            ),
            (
                "relation_type_formatted"
            ): relation_label,
            "anilist_data": edge,
        }

        if media_type == "ANIME":
            related_anime.append(
                item
            )

        else:
            related_manga.append(
                item
            )

    return (
        related_anime,
        related_manga,
    )


def normalize_anilist_node(
    node,
):
    title_data = (
        node.get("title")
        or {}
    )

    cover_data = (
        node.get("coverImage")
        or {}
    )

    media_type = (
        node.get("type")
        or ""
    ).upper()

    return {
        "id": node.get("idMal"),
        "title": (
            title_data.get("romaji")
            or title_data.get("english")
            or title_data.get("native")
            or ""
        ),
        "alternative_titles": {
            "en": (
                title_data.get("english")
                or ""
            ),
            "ja": (
                title_data.get("native")
                or ""
            ),
        },
        "main_picture": {
            "large": (
                cover_data.get(
                    "extraLarge"
                )
                or cover_data.get(
                    "large"
                )
                or ""
            ),
            "medium": (
                cover_data.get(
                    "medium"
                )
                or ""
            ),
        },
        "media_type": (
            str(
                node.get("format")
                or media_type
            )
            .lower()
        ),
        "status": (
            normalize_anilist_status(
                node.get("status"),
                media_type=media_type,
            )
        ),
        "num_episodes": (
            node.get("episodes")
            or 0
        ),
        "num_chapters": (
            node.get("chapters")
            or 0
        ),
        "num_volumes": (
            node.get("volumes")
            or 0
        ),
        "start_date": (
            anilist_date_to_string(
                node.get("startDate")
            )
        ),
        "end_date": (
            anilist_date_to_string(
                node.get("endDate")
            )
        ),
        "anilist_id": (
            node.get("id")
        ),
    }


def normalize_anilist_status(
    status,
    *,
    media_type,
):
    if media_type == "ANIME":
        mapping = {
            "RELEASING": (
                "currently_airing"
            ),
            "FINISHED": (
                "finished_airing"
            ),
            "NOT_YET_RELEASED": (
                "not_yet_aired"
            ),
        }

    else:
        mapping = {
            "RELEASING": (
                "currently_publishing"
            ),
            "FINISHED": "finished",
            "HIATUS": "on_hiatus",
            "NOT_YET_RELEASED": (
                "not_yet_published"
            ),
            "CANCELLED": (
                "discontinued"
            ),
        }

    return mapping.get(
        status,
        (
            str(status).lower()
            if status
            else ""
        ),
    )


def anilist_date_to_string(
    value,
):
    if not value:
        return None

    year = value.get("year")

    if not year:
        return None

    month = value.get("month")
    day = value.get("day")

    if not month:
        return str(year)

    if not day:
        return (
            f"{year:04d}-"
            f"{month:02d}"
        )

    return (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )


def prune_stale_relations(
    *,
    source_mal_id,
    related_anime,
    related_manga,
):
    current_keys = {
        (
            item["node"]["id"],
            "anime",
            item["relation_type"],
        )
        for item in related_anime
    }

    current_keys.update(
        {
            (
                item["node"]["id"],
                "manga",
                item["relation_type"],
            )
            for item in related_manga
        }
    )

    existing_relations = (
        MangaRelation.objects
        .filter(
            source_mal_id=(
                source_mal_id
            )
        )
    )

    stale_ids = [
        relation.pk
        for relation in existing_relations
        if (
            relation.target_mal_id,
            relation.relation_source_type,
            relation.relation_type,
        )
        not in current_keys
    ]

    if stale_ids:
        (
            MangaRelation.objects
            .filter(
                pk__in=stale_ids
            )
            .delete()
        )

def save_raw_json(
    manga_id,
    data,
):
    raw_dir = (
        settings.BASE_DIR
        / "data"
        / "raw"
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    output_file = (
        raw_dir
        / (
            "manga_relations_"
            f"{manga_id}_"
            f"{timestamp}.json"
        )
    )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


def save_relations(
    *,
    source_manga,
    source_mal_id,
    source_title,
    items,
    relation_source_type,
):
    created_count = 0
    updated_count = 0

    for item in items:
        node = item.get(
            "node",
            {},
        )

        target_mal_id = (
            node.get("id")
        )

        if target_mal_id is None:
            continue

        target_title = (
            node.get("title")
            or ""
        )

        main_picture = (
            node.get(
                "main_picture"
            )
            or {}
        )

        if (
            relation_source_type
            == "anime"
        ):
            save_anime_metadata_from_node(
                node
            )

        local_status = (
            get_target_local_status(
                target_mal_id=(
                    target_mal_id
                ),
                relation_source_type=(
                    relation_source_type
                ),
            )
        )

        defaults = {
            "source_manga": (
                source_manga
            ),
            "source_title": (
                source_title
            ),
            "target_title": (
                target_title
            ),
            "target_media_type": (
                node.get(
                    "media_type"
                )
            ),
            "target_status": (
                node.get(
                    "status"
                )
            ),
            "target_picture_url": (
                main_picture.get(
                    "large"
                )
                or main_picture.get(
                    "medium"
                )
            ),
            "target_num_episodes": (
                node.get(
                    "num_episodes"
                )
                or 0
            ),
            "target_num_chapters": (
                node.get(
                    "num_chapters"
                )
                or 0
            ),
            "target_num_volumes": (
                node.get(
                    "num_volumes"
                )
                or 0
            ),
            (
                "relation_type_formatted"
            ): item.get(
                "relation_type_formatted"
            ),
            "target_local_list_status": (
                local_status
            ),
            "raw_data": item,
            "last_synced_at": (
                timezone.now()
            ),
        }

        _relation, created = (
            MangaRelation.objects
            .update_or_create(
                source_mal_id=(
                    source_mal_id
                ),
                target_mal_id=(
                    target_mal_id
                ),
                relation_source_type=(
                    relation_source_type
                ),
                relation_type=(
                    item.get(
                        "relation_type"
                    )
                    or ""
                ),
                defaults=defaults,
            )
        )

        if created:
            created_count += 1

        else:
            updated_count += 1

    return (
        created_count,
        updated_count,
    )


def get_target_local_status(
    *,
    target_mal_id,
    relation_source_type,
):
    if (
        relation_source_type
        == "anime"
    ):
        target = (
            AnimeEntry.objects
            .filter(
                mal_id=target_mal_id
            )
            .first()
        )

    elif (
        relation_source_type
        == "manga"
    ):
        target = (
            MangaEntry.objects
            .filter(
                mal_id=target_mal_id
            )
            .first()
        )

    else:
        return ""

    return (
        target.list_status
        if target
        else ""
    )


def save_anime_metadata_from_node(
    node,
):
    mal_id = node.get("id")

    if mal_id is None:
        return None

    main_picture = (
        node.get(
            "main_picture"
        )
        or {}
    )

    alternative_titles = (
        node.get(
            "alternative_titles"
        )
        or {}
    )

    metadata, _created = (
        AnimeMetadata.objects
        .update_or_create(
            mal_id=mal_id,
            defaults={
                "title": (
                    node.get(
                        "title"
                    )
                    or ""
                ),
                "title_japanese": (
                    alternative_titles
                    .get(
                        "ja",
                        "",
                    )
                ),
                "title_english": (
                    alternative_titles
                    .get(
                        "en",
                        "",
                    )
                ),
                "main_picture_url": (
                    main_picture.get(
                        "large"
                    )
                    or main_picture.get(
                        "medium"
                    )
                    or ""
                ),
                "media_type": (
                    node.get(
                        "media_type"
                    )
                    or ""
                ),
                "airing_status": (
                    node.get(
                        "status"
                    )
                    or ""
                ),
                "num_episodes": (
                    node.get(
                        "num_episodes"
                    )
                    or 0
                ),
                "start_date": (
                    normalize_mal_date(
                        node.get(
                            "start_date"
                        )
                    )
                ),
                "end_date": (
                    normalize_mal_date(
                        node.get(
                            "end_date"
                        )
                    )
                ),
                "raw_data": node,
                "last_synced_at": (
                    timezone.now()
                ),
            },
        )
    )

    return metadata


def normalize_mal_date(value):
    if not value:
        return None

    if len(value) == 4:
        return (
            f"{value}-01-01"
        )

    if len(value) == 7:
        return f"{value}-01"

    return value

