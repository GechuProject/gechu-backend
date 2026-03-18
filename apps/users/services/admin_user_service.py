from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.recommendations.models import RecommendationJob
from apps.users.models.user import User


def list_admin_users() -> QuerySet[User]:
    return User.objects.order_by("-created_at")


def get_admin_user(*, user_id: int) -> User:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND) from None


def update_admin_user_status(*, user_id: int, is_active: bool) -> User:
    user = get_admin_user(user_id=user_id)
    user.is_active = is_active
    user.save(update_fields=["is_active", "updated_at"])
    return user


def get_admin_dashboard_summary() -> dict[str, int]:
    today = timezone.localdate()
    visible_users = User.objects.filter(deleted_at__isnull=True)

    return {
        "total_users": visible_users.count(),
        "active_users": visible_users.filter(is_active=True).count(),
        "recommendation_jobs_today": RecommendationJob.objects.filter(created_at__date=today).count(),
        "failed_jobs": RecommendationJob.objects.filter(status=RecommendationJob.Status.FAILED).count(),
    }
