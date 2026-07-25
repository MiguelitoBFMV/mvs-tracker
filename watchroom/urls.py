from django.urls import path

from .web import dashboard as dashboard_views
from .web import detail as detail_views
from .web import library as library_views


app_name = "watchroom"


urlpatterns = [
    path(
        "",
        dashboard_views.dashboard,
        name="dashboard",
    ),
    path(
        "library/",
        library_views.library,
        name="library",
    ),
    path(
        "library/<slug:slug>/",
        detail_views.detail,
        name="detail",
    ),
]