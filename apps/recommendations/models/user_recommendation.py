from django.conf import settings
from django.db import models


class UserRecommendation(models.Model):
    class ReasonType(models.TextChoices):
        SIMILARITY = "similarity", "유사 게임 기반"
        PREFERENCE = "preference", "선호 기반"
        HYBRID = "hybrid", "혼합 추천"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="recommended_to_users",
    )

    generation_version = models.IntegerField(
        default=1,
    )

    score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
    )

    rank = models.IntegerField()

    reason = models.CharField(
        max_length=20,
        choices=ReasonType.choices,
        null=True,
        blank=True,
    )

    generated_at = models.DateTimeField()

    expires_at = models.DateTimeField()

    class Meta:
        db_table = "user_recommendations"
        constraints = [models.UniqueConstraint(fields=["user", "game"], name="unique_user_game_recommendation")]
        ordering = ["rank"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.game_id} (rank {self.rank})"
