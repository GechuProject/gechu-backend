from django.db import models


# 외부 스토어
class ExternalStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)
    domain = models.CharField(max_length=100)
    icon_url = models.CharField(max_length=255, default="", blank=True)

    class Meta:
        db_table = "external_stores"

    def __str__(self) -> str:
        return self.name


# 게임스토어
class GameStore(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_stores")
    store = models.ForeignKey("ExternalStore", on_delete=models.CASCADE, related_name="game_stores")
    url = models.CharField(max_length=255)

    class Meta:
        db_table = "game_stores"
        unique_together = ("game", "store")

    def __str__(self) -> str:
        return f"{self.game.name} - {self.store.name}"
