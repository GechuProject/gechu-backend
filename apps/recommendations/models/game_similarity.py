from django.db import models

from apps.core.models import TimeStampedModel

class GameSimilarity(TimeStampedModel):

    game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="similar_games_from",
    )

    similar_game = models.ForeignKey(
        "games.Game",
        on_delete=models.CASCADE,
        related_name="similar_games_to",
    )

    score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
    )

    class Meta:
        db_table = "game_similarities"
        constraints = [
            models.UniqueConstraint(
                fields=["game", "similar_game"],
                name="unique_game_similarity_pair",
            )
        ]
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["similar_game"]),
        ]

    def __str__(self) -> str:
        return f"{self.game_id} ↔ {self.similar_game_id} ({self.score})"