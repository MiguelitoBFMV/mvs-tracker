import json
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from mal_data.models import AnimeEntry, AnimeMetadata, AnimeRelation, MangaEntry
from mal_data.services.anilist_client import (
    AniListClient,
)
from mal_data.services.manga_relations_sync import (
    normalize_anilist_relations,
)


def sync_anime_relations(
    anime_id,
    save_raw=True,
):
    client = AniListClient()

    data = (
        client
        .fetch_anime_relations_by_mal_id(
            anime_id
        )
    )

    if not data:
        raise ValueError(
            "AniList returned no anime "
            "for this MAL ID."
        )

    if save_raw:
        save_raw_json(
            anime_id,
            data,
        )

    source_mal_id = (
        data.get("idMal")
        or anime_id
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

    source_anime = (
        AnimeEntry.objects
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
        source_anime=source_anime,
        source_mal_id=source_mal_id,
        source_title=source_title,
        items=related_anime,
        relation_source_type="anime",
    )

    (
        manga_created,
        manga_updated,
    ) = save_relations(
        source_anime=source_anime,
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
        AnimeRelation.objects
        .filter(
            source_mal_id=(
                source_mal_id
            )
        )
    )

    stale_ids = [
        relation.pk
        for relation
        in existing_relations
        if (
            relation.target_mal_id,
            relation.relation_source_type,
            relation.relation_type,
        )
        not in current_keys
    ]

    if stale_ids:
        (
            AnimeRelation.objects
            .filter(
                pk__in=stale_ids
            )
            .delete()
        )

def save_raw_json(anime_id, data):
    raw_dir = settings.BASE_DIR / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = raw_dir / f"anime_relations_{anime_id}_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    return output_file

def save_relations(
    source_anime,
    source_mal_id,
    source_title,
    items,
    relation_source_type,
):
    created_count = 0
    updated_count = 0

    for item in items:
        node = item.get("node", {})
        main_picture = node.get("main_picture") or {}

        target_mal_id = node.get("id")
        target_title = node.get("title") or ""

        if target_mal_id is None:
            continue
        
        if relation_source_type == "anime":
            save_anime_metadata_from_relation_node(node)

        target_local_list_status = get_target_local_status(
            target_mal_id=target_mal_id,
            relation_source_type=relation_source_type,
        )

        defaults = {
            "source_anime": source_anime,
            "source_title": source_title,
            "target_title": target_title,
            "target_media_type": node.get("media_type"),
            "target_status": node.get("status"),
            "target_picture_url": main_picture.get("large") or main_picture.get("medium"),
            "relation_type_formatted": item.get("relation_type_formatted"),
            "target_local_list_status": target_local_list_status,
            "raw_data": item,
            "last_synced_at": timezone.now(),
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
        }

        _, created = AnimeRelation.objects.update_or_create(
            source_mal_id=source_mal_id,
            target_mal_id=target_mal_id,
            relation_source_type=relation_source_type,
            relation_type=item.get("relation_type") or "",
            defaults=defaults,
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count

def get_target_local_status(target_mal_id, relation_source_type):
    if relation_source_type == "anime":
        target = AnimeEntry.objects.filter(mal_id=target_mal_id).first()
        return target.list_status if target else ""

    if relation_source_type == "manga":
        target = MangaEntry.objects.filter(mal_id=target_mal_id).first()
        return target.list_status if target else ""

    return ""

def save_anime_metadata_from_relation_node(node):
    main_picture = node.get("main_picture") or {}
    alternative_titles = node.get("alternative_titles") or {}

    mal_id = node.get("id")
    title = node.get("title") or ""

    if mal_id is None:
        return None

    metadata, _ = AnimeMetadata.objects.update_or_create(
        mal_id=mal_id,
        defaults={
            "title": title,
            "title_japanese": alternative_titles.get("ja", ""),
            "title_english": alternative_titles.get("en", ""),
            "main_picture_url": main_picture.get("large") or main_picture.get("medium") or "",
            "media_type": node.get("media_type") or "",
            "airing_status": node.get("status") or "",
            "num_episodes": node.get("num_episodes") or 0,
            "start_date": normalize_mal_date(node.get("start_date")),
            "end_date": normalize_mal_date(node.get("end_date")),
            "raw_data": node,
            "last_synced_at": timezone.now(),
        },
    )

    return metadata

def normalize_mal_date(value):
    if not value:
        return None

    if len(value) == 4:
        return f"{value}-01-01"

    if len(value) == 7:
        return f"{value}-01"

    return value