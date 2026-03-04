from django.db import models

class GameTag(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_tags")
    tag = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="game_tags")

    class Meta:
        db_table = "game_tags"
        unique_together = ("game", "tag")
