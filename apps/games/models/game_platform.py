from django.db import models

class GamePlatform(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_platforms")
    platform = models.ForeignKey("Platform", on_delete=models.CASCADE, related_name="game_platforms")
    requirements_minimum = models.TextField(default="", blank=True)
    requirements_recommended = models.TextField(default="", blank=True)

    class Meta:
        db_table = "game_platforms"
        unique_together = ("game", "platform")