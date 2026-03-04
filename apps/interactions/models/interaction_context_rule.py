from django.db import models


class InteractionContextRule(models.Model):
    class InteractionSource(models.TextChoices):
        LIST_PAGE = "list_page", "목록 페이지"
        DETAIL_PAGE = "detail_page", "상세 페이지"
        SEARCH_RESULT = "search_result", "검색 결과"
        RECOMMENDATION = "recommendation", "추천 영역"
        SAVED_PAGE = "saved_page", "찜 목록"
        ONBOARDING = "onboarding", "온보딩"

    interaction_source = models.CharField(
        max_length=30,
        choices=InteractionSource.choices,
        primary_key=True,
    )

    multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "interaction_context_rules"

    def __str__(self) -> str:
        return f"{self.interaction_source} x{self.multiplier}"
