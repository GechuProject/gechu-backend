from django.conf import settings
from django.db import models


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "genres"

    def __str__(self) -> str:
        return self.name


class Platform(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "platforms"

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "tags"

    def __str__(self) -> str:
        return self.name


class UserPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preference",
    )
    genres = models.ManyToManyField(Genre, blank=True, related_name="user_preferences")
    platforms = models.ManyToManyField(Platform, blank=True, related_name="user_preferences")
    tags = models.ManyToManyField(Tag, blank=True, related_name="user_preferences")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_preferences"
