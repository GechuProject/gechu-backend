from django.urls import path

from apps.users.views_admin import (
    AdminDashboardSummaryAPIView,
    AdminUserDetailAPIView,
    AdminUserListAPIView,
)

urlpatterns = [
    path("dashboard/", AdminDashboardSummaryAPIView.as_view(), name="admin-dashboard-summary"),
    path("", AdminUserListAPIView.as_view(), name="admin-user-list"),
    path("<int:user_id>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail"),
]
