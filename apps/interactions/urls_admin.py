from django.urls import path

from apps.interactions.views_admin import AdminInteractionWeightRuleListView

urlpatterns = [
    path("", AdminInteractionWeightRuleListView.as_view(), name="admin-interaction-weight-rule-list"),
]
