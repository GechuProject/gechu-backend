from typing import Any

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.preferences.models import UserPreference

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_preference(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """
    유저(User)가 생성(created=True)될 때,
    해당 유저와 1:1로 연결되는 UserPreference를 자동 생성
    """
    if created:
        UserPreference.objects.get_or_create(user=instance)