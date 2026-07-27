from django.contrib import admin

from .models import (
    Franchise,
    FranchiseMembership,
    MediaWork,
    Season,
    SeasonProgress,
    ViewingRun,
    WatchEntry,
)


class FranchiseMembershipInline(
    admin.TabularInline
):
    model = FranchiseMembership
    extra = 0
    autocomplete_fields = (
        "media_work",
    )
    fields = (
        "media_work",
        "position",
        "role",
        "notes",
    )


@admin.register(Franchise)
class FranchiseAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "tmdb_collection_id",
        "member_count",
        "updated_at",
    )
    search_fields = (
        "name",
        "tmdb_collection_id",
    )
    readonly_fields = (
        "slug",
        "tmdb_synced_at",
        "created_at",
        "updated_at",
    )
    inlines = (
        FranchiseMembershipInline,
    )

    @admin.display(
        description="Works"
    )
    def member_count(
        self,
        franchise,
    ):
        return (
            franchise.memberships
            .count()
        )


@admin.register(
    FranchiseMembership
)
class FranchiseMembershipAdmin(
    admin.ModelAdmin
):
    list_display = (
        "franchise",
        "position",
        "media_work",
        "role",
        "updated_at",
    )
    list_filter = (
        "role",
        "media_work__media_type",
        "media_work__presentation",
    )
    search_fields = (
        "franchise__name",
        "media_work__title",
        "media_work__original_title",
    )
    autocomplete_fields = (
        "franchise",
        "media_work",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(MediaWork)
class MediaWorkAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "media_type",
        "presentation",
        "first_release_date",
        "tmdb_id",
        "updated_at",
    )
    list_filter = (
        "media_type",
        "presentation",
        "external_status",
    )
    search_fields = (
        "title",
        "original_title",
        "tmdb_id",
    )
    readonly_fields = (
        "slug",
        "tmdb_synced_at",
        "created_at",
        "updated_at",
    )


@admin.register(WatchEntry)
class WatchEntryAdmin(admin.ModelAdmin):
    list_display = (
        "media_work",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "media_work__media_type",
        "media_work__presentation",
    )
    search_fields = (
        "media_work__title",
        "media_work__original_title",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = (
        "media_work",
        "season_number",
        "name",
        "episode_count",
        "air_date",
        "tmdb_id",
    )
    list_filter = (
        "media_work__presentation",
        "air_date",
    )
    search_fields = (
        "media_work__title",
        "name",
        "tmdb_id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(ViewingRun)
class ViewingRunAdmin(admin.ModelAdmin):
    list_display = (
        "watch_entry",
        "number",
        "status",
        "started_on",
        "finished_on",
        "progress_minutes",
        "updated_at",
    )
    list_filter = (
        "status",
        "watch_entry__media_work__media_type",
        "watch_entry__media_work__presentation",
    )
    search_fields = (
        "watch_entry__media_work__title",
        "notes",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(SeasonProgress)
class SeasonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "viewing_run",
        "season",
        "episodes_watched",
        "updated_at",
    )
    list_filter = (
        "season__media_work__presentation",
        "season__season_number",
    )
    search_fields = (
        "season__media_work__title",
        "season__name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


