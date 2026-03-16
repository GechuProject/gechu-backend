from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.users.models import User

SOFT_DELETE_RETENTION_DAYS = 7


@shared_task
def purge_soft_deleted_users() -> int:
    cutoff = timezone.now() - timedelta(days=SOFT_DELETE_RETENTION_DAYS)
    queryset = User.objects.filter(deleted_at__isnull=False, deleted_at__lte=cutoff)
    deleted_user_count = queryset.count()
    queryset.delete()
    return deleted_user_count
