from datetime import date, timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models.adult_verification import AdultVerification

User = get_user_model()


class Command(BaseCommand):
    help = "Create development test users"

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()

        # 일반 유저
        normal_user, _ = User.objects.get_or_create(
            email="user@test.com",
            defaults={
                "nickname": "normal_user",
                "birth_date": date(2000, 1, 1),
                "is_active": True,
            },
        )
        normal_user.set_password("user")
        normal_user.save()

        self.stdout.write(self.style.SUCCESS("Normal user ready"))

        # 성인 인증 유저
        adult_user, _ = User.objects.get_or_create(
            email="adult@test.com",
            defaults={
                "nickname": "adult_user",
                "birth_date": date(1995, 6, 15),
                "is_active": True,
            },
        )

        adult_user.is_adult_verified = True
        adult_user.adult_verified_at = now
        adult_user.adult_verification_expires_at = now + timedelta(days=365)
        adult_user.set_password("adult")
        adult_user.save()

        AdultVerification.objects.get_or_create(
            user=adult_user,
            provider=AdultVerification.Provider.BBATON,
            provider_uid="bbaton_test_uid_123",
            defaults={
                "verified_at": now,
                "expires_at": now + timedelta(days=365),
                "raw_payload": {"mock": True},
            },
        )

        self.stdout.write(self.style.SUCCESS("Adult verified user ready"))

        # 비활성 유저
        inactive_user, _ = User.objects.get_or_create(
            email="inactive@test.com",
            defaults={
                "nickname": "inactive_user",
                "birth_date": date(1998, 5, 5),
                "is_active": False,
            },
        )
        inactive_user.set_password("inactive")
        inactive_user.is_active = False
        inactive_user.save()

        self.stdout.write(self.style.SUCCESS("Inactive user ready"))

        # 어드민 유저
        admin_user, _ = User.objects.get_or_create(
            email="admin@test.com",
            defaults={
                "nickname": "admin",
                "birth_date": date(1990, 1, 1),
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password("admin")
        admin_user.save()

        self.stdout.write(self.style.SUCCESS("Admin user ready"))

        self.stdout.write(self.style.SUCCESS("All test users seeded"))
