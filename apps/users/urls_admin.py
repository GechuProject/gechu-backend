from django.urls import path

from apps.interactions.views_admin_user import AdminUserInteractionListView
from apps.recommendations.views_admin import AdminUserRecommendationListView
from apps.users.views_admin import (
    AdminDashboardSummaryAPIView,
    AdminUserDetailAPIView,
    AdminUserListAPIView,
)

urlpatterns = [
    path("dashboard/", AdminDashboardSummaryAPIView.as_view(), name="admin-dashboard-summary"),
    path("", AdminUserListAPIView.as_view(), name="admin-user-list"),
    path("<int:user_id>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail"),
    path(
        "<int:user_id>/recommendations/",
        AdminUserRecommendationListView.as_view(),
        name="admin-user-recommendation-list",
    ),
    path(
        "<int:user_id>/interactions/",
        AdminUserInteractionListView.as_view(),
        name="admin-user-interaction-list",
    ),
]
