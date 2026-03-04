from django.db import models


class GameGenre(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_genres")
    genre = models.ForeignKey("Genre", on_delete=models.CASCADE, related_name="game_genres")

    class Meta:
        db_table = "game_genres"
        unique_together = ("game", "genre")
