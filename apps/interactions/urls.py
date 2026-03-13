from django.urls import path

from apps.interactions.views import (
    InteractionSearchLogCreateView,
    InteractionStoreClickLogCreateView,
    InteractionViewLogCreateView,
)

urlpatterns = [
    path("view/", InteractionViewLogCreateView.as_view(), name="interaction-view-create"),
    path("search/", InteractionSearchLogCreateView.as_view(), name="interaction-search-create"),
    path("store-click/", InteractionStoreClickLogCreateView.as_view(), name="interaction-store-click-create"),
]
