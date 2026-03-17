from .game_detail import GameDetailView
from .game_list import GameListView
from .genre_list import GenreListAPIView
from .platform_list import PlatformListAPIView
from .similar_game import SimilarGameListView

__all__ = [
    "GameDetailView",
    "GameListView",
    "GenreListAPIView",
    "PlatformListAPIView",
    "SimilarGameListView",
]
