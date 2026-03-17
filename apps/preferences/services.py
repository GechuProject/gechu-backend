from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.interactions.models import InteractionLog
from apps.preferences.models import (
    UserGameAffinity,
    UserPreference,
    UserPreferenceGenre,
    UserPreferencePlatform,
    UserPreferenceTag,
)

if TYPE_CHECKING:
    from apps.users.models import User


def update_user_preferences(
    user: User, genre_ids: list[int], platform_ids: list[int], tag_ids: list[int]
) -> UserPreference:
    """선호 장르/플랫폼/태그 전체 교체 (Replace)"""

    pref, _ = UserPreference.objects.get_or_create(user=user)

    with transaction.atomic():
        pref.userpreferencegenre_set.all().delete()
        pref.userpreferenceplatform_set.all().delete()
        pref.userpreferencetag_set.all().delete()

        if genre_ids:
            UserPreferenceGenre.objects.bulk_create(
                [UserPreferenceGenre(user_preference=pref, genre_id=gid) for gid in genre_ids]
            )
        if platform_ids:
            UserPreferencePlatform.objects.bulk_create(
                [UserPreferencePlatform(user_preference=pref, platform_id=pid) for pid in platform_ids]
            )
        if tag_ids:
            UserPreferenceTag.objects.bulk_create(
                [UserPreferenceTag(user_preference=pref, tag_id=tid) for tid in tag_ids]
            )
    return pref


def update_game_interaction(
    user: User, game_id: int, interaction_source: str, is_saved: bool | None = None, reaction: str | None = None
) -> UserGameAffinity:
    """Affinity Upsert 및 Interaction 로그 기록 (game_id = IGDB game ID)"""
    now = timezone.now()
    affinity, _ = UserGameAffinity.objects.get_or_create(
        user=user, igdb_game_id=game_id, defaults={"last_interacted_at": now, "calculated_at": now}
    )

    reaction_map = {"like": 1, "neutral": 0, "dislike": -1}

    with transaction.atomic():
        has_changed = False

        if reaction is not None:
            new_state = reaction_map.get(reaction)
            if new_state is None:
                raise CustomAPIException(ErrorMessages.INVALID_REACTION)

            if affinity.like_state != new_state:
                affinity.like_state = new_state
                InteractionLog.objects.create(
                    user=user,
                    igdb_game_id=game_id,
                    type=reaction,
                    source=interaction_source,
                )
                has_changed = True

        if is_saved is not None:
            if affinity.is_saved != is_saved:
                affinity.is_saved = is_saved
                action_type = "saved_add" if is_saved else "saved_remove"
                InteractionLog.objects.create(
                    user=user, igdb_game_id=game_id, type=action_type, source=interaction_source
                )
                has_changed = True

        if has_changed:
            affinity.last_interacted_at = now
            affinity.save()

    return affinity


def get_saved_games(user: User) -> QuerySet[UserGameAffinity]:
    return UserGameAffinity.objects.filter(user=user, is_saved=True).order_by("-last_interacted_at")


def get_game_affinities(user: User) -> QuerySet[UserGameAffinity]:
    return UserGameAffinity.objects.filter(user=user).order_by("-preference_score")
