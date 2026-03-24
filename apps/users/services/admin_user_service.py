from __future__ import annotations

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.recommendations.models import RecommendationJob
from apps.users.models.user import User
from apps.users.services.auth_service import revoke_all_refresh_tokens


def list_admin_users() -> QuerySet[User]:
    return User.objects.order_by("-created_at")


def get_admin_user(*, user_id: int) -> User:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise CustomAPIException(ErrorMessages.USER_NOT_FOUND) from None


def update_admin_user_status(*, user_id: int, is_active: bool) -> User:
    user = get_admin_user(user_id=user_id)
    status_changed = user.is_active != is_active
    user.is_active = is_active
    update_fields = ["is_active", "updated_at"]
    if is_active and user.deleted_at is not None:
        user.deleted_at = None
        update_fields.append("deleted_at")
        status_changed = True
    user.save(update_fields=update_fields)
    if status_changed:
        revoke_all_refresh_tokens(user)
    return user


def get_admin_dashboard_summary() -> dict[str, int]:
    today = timezone.localdate()
    user_summary = User.objects.filter(deleted_at__isnull=True).aggregate(
        total_users=Count("id"),
        active_users=Count("id", filter=Q(is_active=True)),
    )
    job_summary = RecommendationJob.objects.aggregate(
        recommendation_jobs_today=Count("id", filter=Q(created_at__date=today)),
        failed_jobs=Count("id", filter=Q(status=RecommendationJob.Status.FAILED)),
    )

    return {
        "total_users": int(user_summary["total_users"]),
        "active_users": int(user_summary["active_users"]),
        "recommendation_jobs_today": int(job_summary["recommendation_jobs_today"]),
        "failed_jobs": int(job_summary["failed_jobs"]),
    }
