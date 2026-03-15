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
