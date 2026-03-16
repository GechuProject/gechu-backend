from django.urls import path

from apps.interactions.views_admin import (
    AdminInteractionWeightRuleListView,
    AdminInteractionWeightRuleUpdateView,
)

urlpatterns = [
    path("", AdminInteractionWeightRuleListView.as_view(), name="admin-interaction-weight-rule-list"),
    path(
        "<str:interaction_type>/",
        AdminInteractionWeightRuleUpdateView.as_view(),
        name="admin-interaction-weight-rule-update",
    ),
]
