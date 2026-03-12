from __future__ import annotations

import json
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
    if metadata is not None:
        try:
            json.dumps(metadata)
        except (TypeError, ValueError):
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR) from None

    try:
        game = Game.objects.get(id=game_id, is_visible=True)
    except Game.DoesNotExist:
        raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND) from None

    try:
        weight_rule = InteractionWeightRule.objects.get(
            interaction_type=InteractionLog.ActionType.VIEW,
            is_active=True,
        )
    except InteractionWeightRule.DoesNotExist:
        raise CustomAPIException(ErrorMessages.INTERACTION_TYPE_NOT_FOUND) from None

    try:
        context_rule = InteractionContextRule.objects.get(interaction_source=source)
    except InteractionContextRule.DoesNotExist:
        raise CustomAPIException(ErrorMessages.SOURCE_NOT_FOUND) from None

    latest_reusable_log = (
        InteractionLog.objects.filter(
            user=user,
            game=game,
            type=InteractionLog.ActionType.VIEW,
            source=source,
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
    effective_repeat_count = min(repeat_count, 10)
    weight: Decimal = (
        weight_rule.base_weight
        * context_rule.multiplier
        * (weight_rule.repeat_decay**effective_repeat_count)
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
