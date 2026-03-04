from django.db import models

class GameStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(
        "Game",
        on_delete=models.CASCADE,
        related_name="game_stores"
    )
    store = models.ForeignKey(
        "ExternalStore",
        on_delete=models.CASCADE,
        related_name="game_stores"
    )
    url = models.CharField(max_length=255)

    class Meta:
        db_table = "game_stores"
        unique_together = ("game", "store")

    def __str__(self) -> str:
        return f"{self.game.name} - {self.store.name}"