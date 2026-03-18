from django.urls import path

from apps.games.views.game_detail import GameDetailView
from apps.games.views.game_list import GameListView
from apps.games.views.genre_list import GenreListAPIView
from apps.games.views.platform_list import PlatformListAPIView
from apps.games.views.similar_game import SimilarGameListView
from apps.games.views.tag_list import TagListAPIView

urlpatterns = [
    path("", GameListView.as_view(), name="game-list"),
    path("genres/", GenreListAPIView.as_view(), name="genre-list"),
    path("platforms/", PlatformListAPIView.as_view(), name="platform-list"),
    path("<int:game_id>/", GameDetailView.as_view(), name="game-detail"),
    path("<int:game_id>/similar/", SimilarGameListView.as_view(), name="similar-game"),
    path("tags/", TagListAPIView.as_view(), name="tag-list"),
]
