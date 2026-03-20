import uuid

from django.db import models

from apps.core.models import TimeStampedModel


class UserProfileImage(TimeStampedModel):
    user = models.OneToOneField("users.User", on_delete=models.CASCADE, related_name="profile_image")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    image_data = models.BinaryField()
    content_type = models.CharField(max_length=50, default="image/webp")

    class Meta:
        db_table = "user_profile_images"
