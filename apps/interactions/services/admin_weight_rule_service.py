from decimal import Decimal

from django.db.models import Case, IntegerField, QuerySet, When

from apps.interactions.models import InteractionWeightRule


class InteractionAdminRuleService:
    @staticmethod
    def list_weight_rules() -> QuerySet[InteractionWeightRule]:
        ordered_types = [
            InteractionWeightRule.ActionType.VIEW,
            InteractionWeightRule.ActionType.SEARCH,
            InteractionWeightRule.ActionType.SAVED_ADD,
            InteractionWeightRule.ActionType.SAVED_REMOVE,
            InteractionWeightRule.ActionType.LIKE,
            InteractionWeightRule.ActionType.DISLIKE,
            InteractionWeightRule.ActionType.PREFERENCE_SET,
            InteractionWeightRule.ActionType.STORE_CLICK,
        ]
        order_case = Case(
            *[
                When(interaction_type=interaction_type, then=index)
                for index, interaction_type in enumerate(ordered_types)
            ],
            default=len(ordered_types),
            output_field=IntegerField(),
        )
        return InteractionWeightRule.objects.all().order_by(order_case)

    @staticmethod
    def get_weight_rule(*, interaction_type: str) -> InteractionWeightRule | None:
        return InteractionWeightRule.objects.filter(interaction_type=interaction_type).first()

    @staticmethod
    def update_weight_rule(
        *,
        interaction_type: str,
        base_weight: Decimal | None = None,
        cooldown_seconds: int | None = None,
        repeat_decay: Decimal | None = None,
    ) -> InteractionWeightRule | None:
        rule = InteractionAdminRuleService.get_weight_rule(interaction_type=interaction_type)
        if rule is None:
            return None

        if base_weight is not None:
            rule.base_weight = base_weight
        if cooldown_seconds is not None:
            rule.cooldown_seconds = cooldown_seconds
        if repeat_decay is not None:
            rule.repeat_decay = repeat_decay

        rule.save()
        return rule
