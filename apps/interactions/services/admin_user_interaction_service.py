from django.db.models import QuerySet

from apps.interactions.models import InteractionLog


class InteractionAdminUserInteractionService:
    """Admin: 특정 유저의 InteractionLog 조회."""

    @classmethod
    def list_interaction_logs(
        cls,
        *,
        user_id: int,
        interaction_type: str | None = None,
    ) -> QuerySet[InteractionLog]:
        qs = InteractionLog.objects.filter(user_id=user_id).order_by("-created_at")
        if interaction_type is not None:
            qs = qs.filter(type=interaction_type)
        return qs
