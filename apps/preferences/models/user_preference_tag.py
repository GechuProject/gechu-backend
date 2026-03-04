from django.db import models

from apps.preferences.models import UserPreference
from apps.games.models import Tag


class UserPreferenceTag(models.Model):
    user_preference = models.ForeignKey(
        UserPreference,
        on_delete=models.CASCADE,
        db_column="user_preference_id",
    )

    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        db_column="tag_id",
    )

    class Meta:
        db_table = "user_preference_tags"

        constraints = [
            models.UniqueConstraint(
                fields=["user_preference", "tag"],
                name="unique_user_preference_tag",
            )
        ]

        indexes = [
            models.Index(fields=["user_preference"]),
            models.Index(fields=["tag"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_preference_id}-{self.tag_id}"