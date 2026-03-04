from django.db import models

from apps.core.models import TimeStampedModel
from apps.users.models import User

class UserPreference(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="preference"
    )

    class Meta:
        db_table = "user_preferences"

    def __str__(self) -> str:
        return f"Preferences of {self.user.email if hasattr(self.user, 'email') else self.user.id}"