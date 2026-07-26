from django.urls import path

from .web import dashboard as dashboard_views
from .web import detail as detail_views
from .web import library as library_views
from .web import owner as owner_views
from .web import tmdb as tmdb_views

app_name = "watchroom"


urlpatterns = [
    path(
        "",
        dashboard_views.dashboard,
        name="dashboard",
    ),
    path(
        "search/",
        tmdb_views.search_tmdb,
        name="tmdb_search",
    ),
    path(
        (
            "import/"
            "<str:media_type>/"
            "<int:tmdb_id>/"
        ),
        tmdb_views.review_tmdb_import,
        name="tmdb_import",
    ),
    path(
        "library/",
        library_views.library,
        name="library",
    ),
    path(
        "library/create/",
        owner_views.create_work,
        name="create_work",
    ),
    path(
        "library/<slug:slug>/entry/update/",
        owner_views.update_entry,
        name="update_entry",
    ),
    path(
        "library/<slug:slug>/seasons/create/",
        owner_views.create_season,
        name="create_season",
    ),
    path(
        (
        "library/<slug:slug>/"
        "seasons/<int:season_id>/update/"
            ),
        owner_views.update_season,
        name="update_season",
    ),
    path(
        (
            "library/<slug:slug>/"
            "seasons/<int:season_id>/delete/"
        ),
        owner_views.delete_season,
        name="delete_season",
    ),
    path(
        "library/<slug:slug>/runs/create/",
        owner_views.create_run,
        name="create_run",
    ),
    path(
        (
            "library/<slug:slug>/"
            "runs/<int:run_id>/update/"
        ),
        owner_views.update_run,
        name="update_run",
    ),
    path(
        (
            "library/<slug:slug>/"
            "runs/<int:run_id>/"
            "<str:action>/"
        ),
        owner_views.transition_run,
        name="transition_run",
    ),
    path(
        (
            "library/<slug:slug>/"
            "runs/<int:run_id>/"
            "progress/<int:season_id>/update/"
        ),
        owner_views.update_season_progress,
        name="update_season_progress",
    ),
    path(
        (
            "library/<slug:slug>/"
            "tmdb/refresh/"
        ),
        tmdb_views.refresh_tmdb_work,
        name="refresh_tmdb",
    ),
    path(
        "library/<slug:slug>/delete/",
        owner_views.delete_work,
        name="delete_work",
    ),
    path(
        "library/<slug:slug>/",
        detail_views.detail,
        name="detail",
    ),
]