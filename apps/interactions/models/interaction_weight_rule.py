from django.db import models

from apps.core.models import TimeStampedModel


class InteractionWeightRule(TimeStampedModel):
    class ActionType(models.TextChoices):
        VIEW = "view", "상세 조회"
        SEARCH = "search", "검색"
        SAVED_ADD = "saved_add", "찜 추가"
        SAVED_REMOVE = "saved_remove", "찜 제거"
        LIKE = "like", "좋아요"
        DISLIKE = "dislike", "싫어요"
        PREFERENCE_SET = "preference_set", "선호 설정"
        STORE_CLICK = "store_click", "스토어 클릭"

    interaction_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
        primary_key=True,
    )

    base_weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
    )

    cooldown_seconds = models.IntegerField(
        default=0,
        help_text="이 시간 내 동일 행동은 무시",
    )

    repeat_decay = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1.000,
        help_text="반복 감소 계수 (1에 가까울수록 감소 적음)",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "interaction_weight_rules"

    def __str__(self) -> str:
        return f"{self.interaction_type} ({self.base_weight})"
