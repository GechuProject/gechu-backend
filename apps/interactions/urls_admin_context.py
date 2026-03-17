from django.urls import path

from apps.interactions.views_admin import (
    AdminInteractionContextRuleListView,
    AdminInteractionContextRuleUpdateView,
)

urlpatterns = [
    path("", AdminInteractionContextRuleListView.as_view(), name="admin-interaction-context-rule-list"),
    path(
        "<str:source>/",
        AdminInteractionContextRuleUpdateView.as_view(),
        name="admin-interaction-context-rule-update",
    ),
]
