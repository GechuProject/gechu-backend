from django.db import models


class GameSimilarity(models.Model):
    igdb_game_id = models.BigIntegerField(
        default=0,
        db_index=True,
        help_text="IGDB 게임 ID",
    )

    igdb_similar_game_id = models.BigIntegerField(
        default=0,
        db_index=True,
        help_text="유사 게임 IGDB ID",
    )

    score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "game_similarities"
        constraints = [
            models.UniqueConstraint(
                fields=["igdb_game_id", "igdb_similar_game_id"],
                name="unique_game_similarity_pair",
            )
        ]
        indexes = [
            models.Index(fields=["igdb_game_id"]),
            models.Index(fields=["igdb_similar_game_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.igdb_game_id} ↔ {self.igdb_similar_game_id} ({self.score})"
