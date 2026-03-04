from django.db import models


class GameMedia(models.Model):
    class MediaType(models.TextChoices):
        SCREENSHOT = "screenshot", "스크린샷"
        TRAILER = "trailer", "트레일러"

    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="media")
    rawg_id = models.BigIntegerField()
    type = models.CharField(max_length=20, choices=MediaType.choices)
    media_url = models.CharField(max_length=255)

    # 트레일러 전용 필드
    video_url_480 = models.CharField(max_length=255, null=True, blank=True)
    video_url_max = models.CharField(max_length=255, null=True, blank=True)
    video_name = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "game_media"
        unique_together = ("game", "rawg_id")

    def __str__(self) -> str:
        return f"{self.game.name} - {self.type} ({self.rawg_id})"
