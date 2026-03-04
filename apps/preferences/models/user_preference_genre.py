from django.db import models

from apps.preferences.models import UserPreference
from apps.games.models import Genre


class UserPreferenceGenre(models.Model):
    user_preference = models.ForeignKey(
        UserPreference,
        on_delete=models.CASCADE,
        db_column="user_preference_id",
    )

    genre = models.ForeignKey(
        Genre,
        on_delete=models.CASCADE,
        db_column="genre_id",
    )

    class Meta:
        db_table = "user_preferences_genres"

        constraints = [
            models.UniqueConstraint(
                fields=["user_preference", "genre"],
                name="unique_user_preference_genre",
            )
        ]

        indexes = [
            models.Index(fields=["user_preference"]),
            models.Index(fields=["genre"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_preference_id}-{self.genre_id}"
