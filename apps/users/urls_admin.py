from django.urls import path

from apps.users.views_admin import (
    AdminUserDetailAPIView,
    AdminUserListAPIView,
)

urlpatterns = [
    path("", AdminUserListAPIView.as_view(), name="admin-user-list"),
    path("<int:user_id>/", AdminUserDetailAPIView.as_view(), name="admin-user-detail"),
]
