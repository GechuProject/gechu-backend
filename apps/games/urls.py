from django.urls import path

from .views.game_detail import GameDetailView
from .views.game_list import GameListView
from .views.genre_list import GenreListAPIView
from .views.similar_game import SimilarGameListView

urlpatterns = [
    path("", GameListView.as_view(), name="game-list"),
    path("<int:game_id>/", GameDetailView.as_view(), name="game-detail"),
    path("<int:game_id>/similar/", SimilarGameListView.as_view(), name="similar-game"),
    path("genres/", GenreListAPIView.as_view(), name="genre-list"),
]
