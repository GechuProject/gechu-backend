from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Game
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
        # 기존 데이터 전체 삭제 (빈 배열이 들어와도 초기화됨)
        pref.userpreferencegenre_set.all().delete()
        pref.userpreferenceplatform_set.all().delete()
        pref.userpreferencetag_set.all().delete()

        # 신규 데이터 Bulk Create
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
    """Affinity Upsert 및 Interaction 로그 기록"""
    try:
        game: Game = Game.objects.get(pk=game_id)
    except Game.DoesNotExist:
        raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND) from None

    # Affinity 존재 확인 및 생성 (Upsert 기초)
    now = timezone.now()
    affinity, _ = UserGameAffinity.objects.get_or_create(
        user=user, game=game, defaults={"last_interacted_at": now, "calculated_at": now}
    )

    # reaction 문자열을 DB 상태값(정수)으로 매핑
    reaction_map = {"like": 1, "neutral": 0, "dislike": -1}

    with transaction.atomic():
        has_changed = False

        # Reaction(좋아요/싫어요) 처리 및 로그 기록
        if reaction is not None:
            new_state = reaction_map.get(reaction)
            if new_state is None:
                raise CustomAPIException(ErrorMessages.INVALID_REACTION)

            if affinity.like_state != new_state:
                affinity.like_state = new_state
                InteractionLog.objects.create(
                    user=user,
                    game=game,
                    type=reaction,
                    source=interaction_source,
                )
                has_changed = True

        # is_saved(찜하기) 처리 및 로그 기록
        if is_saved is not None:
            if affinity.is_saved != is_saved:
                affinity.is_saved = is_saved
                action_type = "saved_add" if is_saved else "saved_remove"
                InteractionLog.objects.create(user=user, game=game, type=action_type, source=interaction_source)
                has_changed = True

        if has_changed:
            affinity.last_interacted_at = now
            affinity.save()

    return affinity


def get_saved_games(user: User) -> QuerySet[UserGameAffinity]:
    return (
        UserGameAffinity.objects.filter(user=user, is_saved=True).select_related("game").order_by("-last_interacted_at")
    )


def get_game_affinities(user: User) -> QuerySet[UserGameAffinity]:
    return UserGameAffinity.objects.filter(user=user).select_related("game").order_by("-preference_score")
