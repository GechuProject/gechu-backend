from django.conf import settings

from apps.core.models import TimeStampedModel
from apps.core import models

class SocialUser(models.Model, TimeStampedModel):
    class Provider(models.TextChoices):
        KAKAO = "KAKAO", "카카오"
        DISCORD = "DISCORD", "디스코드"

    id = models.BigAutoField(primary_key=True)

    # 연결된 유저 (users 테이블 FK)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )

    provider = models.CharField(max_length=20, choices=Provider.choices, null=False, blank=False)

    provider_uid = models.CharField(max_length=255, null=False, blank=False)

    class Meta:
        db_table = "social_users"
        unique_together = ("provider", "provider_uid")

    def __str__(self):
        return f"{self.user.email} - {self.provider}"