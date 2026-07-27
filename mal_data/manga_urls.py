from django.urls import path

from .web import (
    manga_dashboard as dashboard_views,
    manga_sync as sync_views,
    manga_library as library_views,
)


app_name = "manga_insights"


urlpatterns = [
    path(
        "",
        dashboard_views.manga_dashboard,
        name="dashboard",
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
]