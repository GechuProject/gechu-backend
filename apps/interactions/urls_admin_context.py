from django.urls import path

from apps.interactions.views_admin import AdminInteractionContextRuleListView

urlpatterns = [
    path("", AdminInteractionContextRuleListView.as_view(), name="admin-interaction-context-rule-list"),
]
