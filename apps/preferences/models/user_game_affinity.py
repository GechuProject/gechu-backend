from django.db import models

from apps.core.models import TimeStampedModel
from apps.users.models import User


class UserGameAffinity(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
    )

    igdb_game_id = models.BigIntegerField(
        default=0,
        db_index=True,
        help_text="IGDB 게임 ID (외부 API 기준)",
    )

    is_saved = models.BooleanField(default=False)

    class LikeState(models.IntegerChoices):
        DISLIKE = -1, "싫어요"
        NEUTRAL = 0, "중립"
        LIKE = 1, "좋아요"

    like_state = models.SmallIntegerField(
        choices=LikeState.choices,
        default=LikeState.NEUTRAL,
    )

    preference_score = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=0,
    )

    last_interacted_at = models.DateTimeField()

    calculated_at = models.DateTimeField()

    class Meta:
        db_table = "user_game_affinity"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "igdb_game_id"],
                name="unique_user_game_affinity",
            )
        ]

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["igdb_game_id"]),
            models.Index(fields=["like_state"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}-{self.igdb_game_id}"
