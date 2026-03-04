from typing import Any
from django.db import models
from django.conf import settings

from apps.core.models import TimeStampedModel


class InteractionLog(TimeStampedModel):

    class ActionType(models.TextChoices):
        VIEW = "view", "상세 조회"
        SEARCH = "search", "검색"
        SAVED_ADD = "saved_add", "찜 추가"
        SAVED_REMOVE = "saved_remove", "찜 제거"
        LIKE = "like", "좋아요"
        DISLIKE = "dislike", "싫어요"
        PREFERENCE_SET = "preference_set", "선호 설정"
        STORE_CLICK = "store_click", "스토어 클릭"

    class SourceType(models.TextChoices):
        LIST_PAGE = "list_page", "목록 페이지"
        DETAIL_PAGE = "detail_page", "상세 페이지"
        SEARCH_RESULT = "search_result", "검색 결과"
        RECOMMENDATION = "recommendation", "추천 영역"
        SAVED_PAGE = "saved_page", "찜 목록"
        ONBOARDING = "onboarding", "온보딩"

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id",
    )

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        db_column="game_id",
    )

    search_query = models.TextField(
        null=True,
        blank=True,
    )

    type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
    )

    weight = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="행동 발생 시점 가중치 스냅샷",
    )

    source = models.CharField(
        max_length=30,
        choices=SourceType.choices,
    )

    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="추가 정보 (추천 버전, 필터값 등 확장용)",
    )

    class Meta:
        db_table = "interaction_logs"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["game"]),
            models.Index(fields=["type"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise ValueError("InteractionLog는 수정할 수 없습니다 (append-only).")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValueError("InteractionLog는 삭제할 수 없습니다 (append-only).")

    def __str__(self) -> str:
        return f"{self.user_id} - {self.type} - {self.created_at}"