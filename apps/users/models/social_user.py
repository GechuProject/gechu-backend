from django.conf import settings
from django.db import models


class SocialUser(models.Model):
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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_users"
        unique_together = ("provider", "provider_uid")

    def __str__(self) -> str:
        return f"{self.user.email} - {self.provider}"
