from django.conf import settings
from django.db import models


class AdultVerification(models.Model):
    class Provider(models.TextChoices):
        BBATON = "BBATON", "비바톤"

    id = models.BigAutoField(primary_key=True)

    # 연결된 유저 (users 테이블 FK)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="adult_verifications",
    )

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        null=False,
        blank=False,
    )

    provider_uid = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        help_text="인증 제공자 내부 사용자 식별자. 로그인 계정과 무관",
    )

    raw_payload = models.JSONField(null=True, blank=True, help_text="인증 응답 원본 저장 (디버깅/분쟁 대응용)")

    verified_at = models.DateTimeField(null=False, blank=False, help_text="성인 인증이 실제 수행된 시각(event time)")

    expires_at = models.DateTimeField(null=False, blank=False, help_text="verified_at + 정책 기간")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adult_verifications"
        ordering = ["-verified_at"]  # 최신 순 조회

    def __str__(self) -> str:
        return f"{self.user.email} - {self.provider} @ {self.verified_at}"
