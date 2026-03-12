from django.urls import path

from apps.interactions.views import InteractionViewLogCreateView

urlpatterns = [
    path("view/", InteractionViewLogCreateView.as_view(), name="interaction-view-create"),
]
