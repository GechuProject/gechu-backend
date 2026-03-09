from typing import cast

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

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
from apps.preferences.serializers import (
    PreferenceGameReactionUpdateSerializer,
    PreferenceGenresUpdateSerializer,
    PreferenceMeResponseSerializer,
    PreferencePlatformsUpdateSerializer,
    PreferenceTagsUpdateSerializer,
)
from apps.users.models import User


class PreferenceMeRetrieveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = PreferenceMeResponseSerializer(request.user)
        return Response(serializer.data)


class PreferenceMeGenresUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        req_serializer = PreferenceGenresUpdateSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        genre_ids: list[int] = req_serializer.validated_data["genre_ids"]

        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        UserPreferenceGenre.objects.filter(user_preference=pref).delete()
        for gid in genre_ids:
            UserPreferenceGenre.objects.create(user_preference=pref, genre_id=gid)

        response_serializer = PreferenceMeResponseSerializer(request.user)
        return Response(response_serializer.data)


@extend_schema(tags=["Preferences"])
class PreferenceMePlatformsUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        req_serializer = PreferencePlatformsUpdateSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        platform_ids: list[int] = req_serializer.validated_data["platform_ids"]

        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        with transaction.atomic():
            UserPreferencePlatform.objects.filter(user_preference=pref).delete()
            platforms_to_create = [
                UserPreferencePlatform(user_preference=pref, platform_id=pid) for pid in platform_ids
            ]
            UserPreferencePlatform.objects.bulk_create(platforms_to_create)

        response_serializer = PreferenceMeResponseSerializer(request.user)
        return Response(response_serializer.data)


@extend_schema(tags=["Preferences"])
class PreferenceMeTagsUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        req_serializer = PreferenceTagsUpdateSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        tag_ids: list[int] = req_serializer.validated_data["tag_ids"]

        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        with transaction.atomic():
            UserPreferenceTag.objects.filter(user_preference=pref).delete()
            tags_to_create = [UserPreferenceTag(user_preference=pref, tag_id=tid) for tid in tag_ids]
            UserPreferenceTag.objects.bulk_create(tags_to_create)

        response_serializer = PreferenceMeResponseSerializer(request.user)
        return Response(response_serializer.data)


@extend_schema(tags=["Preferences"])
class PreferenceGameReactionUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request, game_id: int) -> Response:
        req_serializer = PreferenceGameReactionUpdateSerializer(data=request.data, partial=True)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        if not Game.objects.filter(pk=game_id, is_visible=True).exists():
            raise CustomAPIException(ErrorMessages.GAME_NOT_FOUND)

        user = cast(User, request.user)
        now = timezone.now()
        affinity, created = UserGameAffinity.objects.update_or_create(
            user=user,
            game_id=game_id,
            defaults={
                "last_interacted_at": now,
                "calculated_at": now,
            },
        )

        logs_to_create = []

        if "is_saved" in data:
            old_saved = affinity.is_saved
            affinity.is_saved = data["is_saved"]
            if old_saved and not data["is_saved"]:
                logs_to_create.append(
                    InteractionLog(
                        user=user,
                        game_id=game_id,
                        type=InteractionLog.ActionType.SAVED_REMOVE,
                        source=InteractionLog.SourceType.DETAIL_PAGE,
                    )
                )
            elif not old_saved and data["is_saved"]:
                logs_to_create.append(
                    InteractionLog(
                        user=user,
                        game_id=game_id,
                        type=InteractionLog.ActionType.SAVED_ADD,
                        source=InteractionLog.SourceType.DETAIL_PAGE,
                    )
                )

        if "reaction" in data:
            reaction_map = {"like": 1, "dislike": -1, "neutral": 0}
            new_state = reaction_map[data["reaction"]]
            old_state = affinity.like_state
            affinity.like_state = new_state
            if old_state != new_state:
                if new_state == 1:
                    logs_to_create.append(
                        InteractionLog(
                            user=user,
                            game_id=game_id,
                            type=InteractionLog.ActionType.LIKE,
                            source=InteractionLog.SourceType.DETAIL_PAGE,
                        )
                    )
                elif new_state == -1:
                    logs_to_create.append(
                        InteractionLog(
                            user=user,
                            game_id=game_id,
                            type=InteractionLog.ActionType.DISLIKE,
                            source=InteractionLog.SourceType.DETAIL_PAGE,
                        )
                    )

        with transaction.atomic():
            affinity.save()
            InteractionLog.objects.bulk_create(logs_to_create)

        return Response(
            {
                "game_id": game_id,
                "is_saved": affinity.is_saved,
                "reaction": {1: "like", -1: "dislike", 0: "neutral"}[affinity.like_state],
                "updated_at": affinity.updated_at,
            },
            status=200,
        )
