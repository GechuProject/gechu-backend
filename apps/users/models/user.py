from datetime import date
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.db import models

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def create_user(
        self,
        email: str,
        nickname: str,
        birth_date: date,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        if not email:
            raise ValueError("이메일을 반드시 입력해야 합니다.")
        email = self.normalize_email(email)
        user = self.model(email=email, nickname=nickname, birth_date=birth_date, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        nickname: str,
        birth_date: date,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("슈퍼유저는 is_staff=True 이어야 합니다.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("슈퍼유저는 is_superuser=True 이어야 합니다.")

        return self.create_user(email, nickname, birth_date, password, **extra_fields)


class User(AbstractBaseUser, TimeStampedModel):
    email = models.EmailField(max_length=254, unique=True)
    nickname = models.CharField(max_length=30, unique=True)
    birth_date = models.DateField()
    profile_img_url = models.CharField(max_length=255, null=True, blank=True)
    is_adult_verified = models.BooleanField(default=False)
    adult_verified_at = models.DateTimeField(null=True, blank=True)
    adult_verification_expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)

    USERNAME_FIELD: str = "email"
    REQUIRED_FIELDS = ["nickname", "birth_date"]

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email
