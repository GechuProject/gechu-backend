from django.db import models


class Genre(models.Model):
    class IgdbType(models.TextChoices):
        GENRE = "genre"
        THEME = "theme"

    id = models.BigAutoField(primary_key=True)
    igdb_id = models.IntegerField(default=0)
    igdb_type = models.CharField(max_length=10, choices=IgdbType.choices, default=IgdbType.GENRE)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "genres"
        constraints = [
            models.UniqueConstraint(fields=["igdb_id", "igdb_type"], name="unique_genre_igdb"),
        ]

    def __str__(self) -> str:
        return self.name


class Platform(models.Model):
    id = models.BigAutoField(primary_key=True)
    igdb_id = models.IntegerField(default=0, unique=True)
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "platforms"

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    class IgdbType(models.TextChoices):
        THEME = "theme"
        KEYWORD = "keyword"
        GAME_MODE = "game_mode"

    id = models.BigAutoField(primary_key=True)
    igdb_id = models.IntegerField(default=0)
    igdb_type = models.CharField(max_length=10, choices=IgdbType.choices, default=IgdbType.THEME)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "tags"
        constraints = [
            models.UniqueConstraint(fields=["igdb_id", "igdb_type"], name="unique_tag_igdb"),
        ]

    def __str__(self) -> str:
        return self.name
