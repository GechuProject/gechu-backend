from django.urls import path

from apps.preferences.views import PreferenceMeRetrieveView

urlpatterns = [
    path("me/", PreferenceMeRetrieveView.as_view(), name="preference-me-retrieve"),
]
