from django.db import models

from apps.preferences.models import UserPreference
from apps.games.models import Platform


class UserPreferencePlatform(models.Model):
    user_preference = models.ForeignKey(
        UserPreference,
        on_delete=models.CASCADE,
        db_column="user_preference_id",
    )

    platform = models.ForeignKey(
        Platform,
        on_delete=models.CASCADE,
        db_column="platform_id",
    )

    class Meta:
        db_table = "user_preference_platforms"

        constraints = [
            models.UniqueConstraint(
                fields=["user_preference", "platform"],
                name="unique_user_preference_platform",
            )
        ]

        indexes = [
            models.Index(fields=["user_preference"]),
            models.Index(fields=["platform"]),
        ]

    def __str__(self):
        return f"{self.user_preference_id}-{self.platform_id}"