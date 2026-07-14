from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anime/status/<str:status>/", views.anime_status_list, name="anime_status_list"),
]