from typing import Any

from django.db import models
from django.utils import timezone


# 게임
class Game(models.Model):
    class EsrbRating(models.TextChoices):
        EVERYONE = "everyone", "전체 이용가"
        EVERYONE_10_PLUS = "everyone_10_plus", "10세 이상"
        TEEN = "teen", "13세 이상"
        MATURE = "mature", "17세 이상"
        ADULTS_ONLY = "adults_only", "성인 전용"
        RATING_PENDING = "rating_pending", "심의 예정"
        UNKNOWN = "unknown", "미분류"

    _ESRB_AGE_MAP: dict[str, int] = {
        EsrbRating.EVERYONE: 0,
        EsrbRating.EVERYONE_10_PLUS: 10,
        EsrbRating.TEEN: 13,
        EsrbRating.MATURE: 17,
        EsrbRating.ADULTS_ONLY: 18,
        EsrbRating.RATING_PENDING: 0,
        EsrbRating.UNKNOWN: 0,
    }

    id = models.BigAutoField(primary_key=True)
    rawg_id = models.BigIntegerField(unique=True)
    slug = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    search_vector = models.TextField(null=True, blank=True)
    released = models.DateField(null=True, blank=True)
    tba = models.BooleanField(default=False)
    thumbnail_img_url = models.CharField(max_length=255)
    website = models.CharField(max_length=255)
    rawg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    rawg_ratings_count = models.IntegerField(default=0)
    metacritic = models.SmallIntegerField(null=True, blank=True)
    rawg_added = models.IntegerField(default=0)
    playtime = models.IntegerField(default=0)

    # ESRB 등급
    esrb_rating = models.CharField(max_length=20, choices=EsrbRating.choices, default=EsrbRating.UNKNOWN)
    age_rating_min = models.SmallIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    rawg_updated = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "games"
        indexes = [
            models.Index(fields=["age_rating_min"], name="IDX_games_age_rating"),
            models.Index(fields=["rawg_rating"], name="IDX_games_rawg_rating"),
            models.Index(fields=["rawg_added"], name="IDX_games_rawg_added"),
            models.Index(fields=["released"], name="IDX_games_released"),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_age_min(cls, esrb_val: str) -> int:
        return cls._ESRB_AGE_MAP.get(esrb_val, 0)

    def save(self, *args: Any, **kwargs: Any) -> None:
        # esrb_rating에 따라 자동으로 age_rating_min 할당
        self.age_rating_min = self.get_age_min(self.esrb_rating)
        super().save(*args, **kwargs)


# 게임장르
class GameGenre(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_genres")
    genre = models.ForeignKey("Genre", on_delete=models.CASCADE, related_name="game_genres")

    class Meta:
        db_table = "game_genres"
        unique_together = ("game", "genre")


# 게임플랫폼
class GamePlatform(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_platforms")
    platform = models.ForeignKey("Platform", on_delete=models.CASCADE, related_name="game_platforms")
    requirements_minimum = models.TextField(default="", blank=True)
    requirements_recommended = models.TextField(default="", blank=True)

    class Meta:
        db_table = "game_platforms"
        unique_together = ("game", "platform")


# 게임태그
class GameTag(models.Model):
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="game_tags")
    tag = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="game_tags")

    class Meta:
        db_table = "game_tags"
        unique_together = ("game", "tag")


# 게임미디어
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
