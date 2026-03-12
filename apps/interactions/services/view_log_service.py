from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
from apps.interactions.models import InteractionContextRule, InteractionLog, InteractionWeightRule
from apps.users.models import User


def record_view_interaction(
    *,
    user: User,
    game_id: int,
    source: str,
    metadata: dict[str, object] | list[object] | str | int | float | bool | None = None,
) -> tuple[InteractionLog, bool]:
    game = Game.objects.filter(id=game_id, is_visible=True).first()
    if game is None:
        raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND)

    weight_rule = InteractionWeightRule.objects.filter(
        interaction_type=InteractionLog.ActionType.VIEW,
        is_active=True,
    ).first()
    if weight_rule is None:
        raise CustomAPIException(ErrorMessages.INTERACTION_TYPE_NOT_FOUND)

    context_rule = InteractionContextRule.objects.filter(
        interaction_source=source,
    ).first()
    if context_rule is None:
        raise CustomAPIException(ErrorMessages.SOURCE_NOT_FOUND)

    latest_reusable_log = (
        InteractionLog.objects.filter(
            user=user,
            game=game,
            type=InteractionLog.ActionType.VIEW,
            weight__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )
    if (
        latest_reusable_log is not None
        and weight_rule.cooldown_seconds > 0
        and latest_reusable_log.created_at >= timezone.now() - timedelta(seconds=weight_rule.cooldown_seconds)
    ):
        return latest_reusable_log, False

    repeat_count = InteractionLog.objects.filter(
        user=user,
        game=game,
        type=InteractionLog.ActionType.VIEW,
    ).count()
    weight: Decimal = (
        weight_rule.base_weight * context_rule.multiplier * (weight_rule.repeat_decay**repeat_count)
    ).quantize(Decimal("0.0001"))

    log = InteractionLog.objects.create(
        user=user,
        game=game,
        type=InteractionLog.ActionType.VIEW,
        source=source,
        weight=weight,
        metadata=metadata,
    )
    return log, True
