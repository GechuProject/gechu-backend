# Create your models here.
from django.db import models
from django.utils import timezone

class Game(models.Model):
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
    esrb_rating = models.CharField(max_length=20, default="unknown")
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

    def __str__(self):
        return self.name
