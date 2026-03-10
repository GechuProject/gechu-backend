from django.urls import path

from apps.preferences.views import (
    GameAffinitiesView,
    PreferenceGameReactionUpdateView,
    PreferenceMeView,
    SavedGamesView,
)

urlpatterns = [
    path("me/", PreferenceMeView.as_view(), name="preference-me"),
    path("me/saved-games/", SavedGamesView.as_view()),
    path("me/game-affinities/", GameAffinitiesView.as_view()),
    path("games/<int:game_id>/", PreferenceGameReactionUpdateView.as_view(), name="preference-game-reaction-update"),
]