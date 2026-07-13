from django.contrib import admin
from .models import MangaEntry


@admin.register(MangaEntry)
class MangaEntryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "list_status",
        "score",
        "num_chapters_read",
        "num_chapters",
        "publication_status",
        "updated_at_mal",
    )

    list_filter = (
        "list_status",
        "publication_status",
        "media_type",
        "is_rereading",
    )

    search_fields = (
        "title",
        "mal_id",
    )

    readonly_fields = (
        "raw_data",
        "last_synced_at",
    )