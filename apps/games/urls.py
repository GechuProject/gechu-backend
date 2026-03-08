from django.urls import path

from .views.game_detail import GameDetailView
from .views.game_list import GameListView

urlpatterns = [
    path("", GameListView.as_view(), name="game-list"),
    path("<int:game_id>/", GameDetailView.as_view(), name="game-detail"),
]
