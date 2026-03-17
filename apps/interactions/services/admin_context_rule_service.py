from django.db.models import Case, IntegerField, QuerySet, When

from apps.interactions.models import InteractionContextRule


class InteractionAdminContextRuleService:
    ORDERED_SOURCES = [
        InteractionContextRule.InteractionSource.LIST_PAGE,
        InteractionContextRule.InteractionSource.DETAIL_PAGE,
        InteractionContextRule.InteractionSource.SEARCH_RESULT,
        InteractionContextRule.InteractionSource.RECOMMENDATION,
        InteractionContextRule.InteractionSource.SAVED_PAGE,
        InteractionContextRule.InteractionSource.ONBOARDING,
    ]

    @classmethod
    def list_context_rules(cls) -> QuerySet[InteractionContextRule]:
        order_case = Case(
            *[When(interaction_source=source, then=index) for index, source in enumerate(cls.ORDERED_SOURCES)],
            default=len(cls.ORDERED_SOURCES),
            output_field=IntegerField(),
        )
        return InteractionContextRule.objects.all().order_by(order_case)
