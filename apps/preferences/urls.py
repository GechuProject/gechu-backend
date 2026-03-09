from django.urls import path

from apps.preferences.views import (
    PreferenceMeGenresUpdateView,
    PreferenceMePlatformsUpdateView,
    PreferenceMeRetrieveView,
    PreferenceMeTagsUpdateView,
)

urlpatterns = [
    path("me/", PreferenceMeRetrieveView.as_view(), name="preference-me-retrieve"),
    path("me/genres/", PreferenceMeGenresUpdateView.as_view(), name="preference-me-genres-update"),
    path("me/platforms/", PreferenceMePlatformsUpdateView.as_view(), name="preference-me-platforms-update"),
    path("me/tags/", PreferenceMeTagsUpdateView.as_view(), name="preference-me-tags-update"),
]
