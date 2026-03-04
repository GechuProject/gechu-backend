from django.db import models

from apps.core.models import TimeStampedModel
from apps.users.models import User
from apps.games.models import Game


class UserGameAffinity(TimeStampedModel):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
    )

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        db_column="game_id",
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
                fields=["user", "game"],
                name="unique_user_game_affinity",
            )
        ]

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["game"]),
            models.Index(fields=["like_state"]),
        ]

    def __str__(self):
        return f"{self.user_id}-{self.game_id}"