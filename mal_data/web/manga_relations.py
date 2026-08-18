from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from mal_data.models import (
    MangaEntry,
    MangaRelation,
)
from mal_data.services.manga_relations_sync import (
    sync_manga_relations,
)


RELATION_TYPE_PRIORITY = {
    "sequel": 0,
    "prequel": 1,
    "parent_story": 2,
    "side_story": 3,
    "spin_off": 4,
    "alternative_version": 5,
    "alternative_setting": 6,
    "summary": 7,
    "full_story": 8,
    "other": 9,
    "character": 10,
}


def relation_sort_key(relation):
    local_group = (
        0
        if relation.has_local_target
        else 1
    )

    return (
        local_group,
        RELATION_TYPE_PRIORITY.get(
            relation.relation_type,
            99,
        ),
        relation.target_display_title.casefold(),
    )


def manga_relations_detail(
    request,
    mal_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    relations = list(
        MangaRelation.objects.filter(
            source_mal_id=mal_id
        )
    )

    relations.sort(
        key=relation_sort_key
    )

    anime_relations = [
        relation
        for relation in relations
        if (
            relation.relation_source_type
            == "anime"
        )
    ]

    manga_relations = [
        relation
        for relation in relations
        if (
            relation.relation_source_type
            == "manga"
        )
    ]

    context = {
        "manga": manga,
        "mal_id": mal_id,
        "source_title": (
            manga.display_title
        ),
        "source_picture_url": (
            manga.main_picture_url
        ),
        "source_status": (
            manga.personal_status_label
        ),
        "source_progress": (
            f"{manga.num_chapters_read} / "
            f"{manga.num_chapters or 'TBD'}"
        ),
        "anime_relations": (
            anime_relations
        ),
        "manga_relations": (
            manga_relations
        ),
        "total_relations": (
            len(relations)
        ),
    }

    return render(
        request,
        (
            "mal_data/"
            "manga_relations_detail.html"
        ),
        context,
    )


@login_required
@require_POST
def sync_manga_relations_view(
    request,
    mal_id,
):
    manga = get_object_or_404(
        MangaEntry,
        mal_id=mal_id,
    )

    try:
        result = sync_manga_relations(
            manga.mal_id
        )

        messages.success(
            request,
            (
                "Relations updated from AniList. "
                f"Anime: "
                f"{result['related_anime_count']} · "
                f"Manga: "
                f"{result['related_manga_count']}"
            ),
        )

    except Exception as error:
        messages.error(
            request,
            (
                "Relation sync failed: "
                f"{error}"
            ),
        )

    return redirect(
        "manga_insights:"
        "manga_relations_detail",
        mal_id=mal_id,
    )

