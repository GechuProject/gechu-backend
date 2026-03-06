from django.urls import path

from .views.game_list import GameListView

urlpatterns = [
    path("", GameListView.as_view(), name="game-list"),
]
