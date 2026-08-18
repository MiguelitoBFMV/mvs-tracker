from django.urls import path

from .web import (
    manga_dashboard as dashboard_views,
    manga_library as library_views,
    manga_source_coverage as coverage_views,
    manga_sources as source_views,
    manga_sync as sync_views,
    manga_search as search_views
)


app_name = "manga_insights"


urlpatterns = [
    path(
        "",
        dashboard_views.manga_dashboard,
        name="dashboard",
    ),
    path(
        "search/",
        search_views.manga_search_view,
        name="manga_search",
    ),
    path(
        "search/rescue/",
        search_views.rescue_manga_from_search_view,
        name="rescue_manga_from_search",
    ),
    path(
        "sources/coverage/",
        coverage_views.manga_source_coverage,
        name="manga_source_coverage",
    ),
    path(
        "<int:mal_id>/sources/",
        source_views.manga_source_management,
        name="manga_source_management",
    ),
    path(
        "<int:mal_id>/sources/save/",
        source_views.save_manga_source,
        name="save_manga_source",
    ),
    path(
        (
            "<int:mal_id>/sources/"
            "<int:link_id>/primary/"
        ),
        source_views
        .make_manga_source_primary_view,
        name="make_manga_source_primary",
    ),
    path(
        (
            "<int:mal_id>/sources/"
            "<int:link_id>/toggle/"
        ),
        source_views
        .toggle_manga_source_active_view,
        name="toggle_manga_source_active",
    ),
    path(
        (
            "<int:mal_id>/sources/"
            "<int:link_id>/unlink/"
        ),
        source_views
        .unlink_manga_source_view,
        name="unlink_manga_source",
    ),
    path(
        "<int:mal_id>/sources/sync/",
        source_views
        .sync_manga_source_now_view,
        name="sync_manga_source_now",
    ),
    path(
        "status/<str:status>/",
        library_views.manga_status_list,
        name="manga_status_list",
    ),
    path(
        "sync/library/",
        sync_views.sync_manga_library_view,
        name="sync_manga_library",
    ),
    path(
        "sync/reading-progress/",
        sync_views.sync_reading_progress_view,
        name="sync_reading_progress",
    ),
    path(
        "sync/manual-rescues/",
        sync_views
        .sync_manual_manga_rescues_view,
        name="sync_manual_manga_rescues",
    ),
]