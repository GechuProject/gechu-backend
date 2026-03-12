from django.urls import path

from .views import (
    GameDetailView,
    GameListView,
    GenreListAPIView,
    PlatformListAPIView,
    SimilarGameListView,
)

urlpatterns = [
    path("", GameListView.as_view(), name="game-list"),
    path("<int:game_id>/", GameDetailView.as_view(), name="game-detail"),
    path("<int:game_id>/similar/", SimilarGameListView.as_view(), name="similar-game"),
    path("genres/", GenreListAPIView.as_view(), name="genre-list"),
    path("platforms/", PlatformListAPIView.as_view(), name="platform-list"),
]
