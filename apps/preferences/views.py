from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.games.igdb import cache as igdb_cache
from apps.preferences.models import (
    UserPreference,
)
from apps.preferences.serializers import (
    GameAffinitySerializer,
    PreferenceGameReactionResponseSerializer,
    PreferenceGameReactionUpdateSerializer,
    PreferenceMeResponseSerializer,
    PreferenceUpdateSerializer,
    SavedGameSerializer,
)
from apps.preferences.services import (
    get_game_affinities,
    get_saved_games,
    update_game_interaction,
    update_user_preferences,
)
from apps.users.models import User

UNSAFE_COOKIE_AUTH_DESCRIPTION = (
    "HttpOnly access_token 쿠키 인증이 필요합니다. "
    "POST, PUT, PATCH, DELETE 요청에는 X-CSRFToken 헤더도 함께 포함해야 합니다."
)


class PreferenceMeView(APIView):
    """
    GET - 내 선호 정보 조회
    PUT - 내 선호 정보 전체 수정 (장르, 플랫폼, 태그)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="내 선호 정보 조회",
        description="현재 로그인한 사용자가 설정한 선호 장르, 플랫폼, 태그 목록을 조회합니다.",
        responses={
            200: inline_serializer(
                name="PreferenceMeResponse",
                fields={
                    "genres": serializers.ListField(
                        child=inline_serializer(
                            name="GenreItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                    "platforms": serializers.ListField(
                        child=inline_serializer(
                            name="PlatformItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                    "tags": serializers.ListField(
                        child=inline_serializer(
                            name="TagItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                },
            ),
            401: OpenApiResponse(description="인증이 필요합니다."),
        },
        tags=["preferences"],
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        pref, _ = UserPreference.objects.get_or_create(user=user)
        return Response(PreferenceMeResponseSerializer(instance=pref).data)

    @extend_schema(
        summary="내 선호 정보 전체 수정",
        description=(
            "사용자의 선호 장르, 플랫폼, 태그를 한 번에 수정(Replace)합니다.\n"
            "- 입력된 리스트로 기존 데이터를 대체합니다.\n"
            "- 모든 필드(genre_ids, platform_ids, tag_ids)는 필수이며 배열 형태여야 합니다."
        ),
        request=PreferenceUpdateSerializer,
        responses={
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
            200: inline_serializer(
                name="PreferenceMeResponse",
                fields={
                    "genres": serializers.ListField(
                        child=inline_serializer(
                            name="GenreItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                    "platforms": serializers.ListField(
                        child=inline_serializer(
                            name="PlatformItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                    "tags": serializers.ListField(
                        child=inline_serializer(
                            name="TagItem",
                            fields={
                                "id": serializers.IntegerField(),
                                "name": serializers.CharField(),
                            },
                        )
                    ),
                },
            ),
            400: OpenApiResponse(description="입력값이 올바르지 않거나 필드가 누락되었습니다."),
            401: OpenApiResponse(description="인증이 필요합니다."),
        },
        tags=["preferences"],
    )
    def put(self, request: Request) -> Response:
        serializer = PreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pref = update_user_preferences(user=cast(User, request.user), **serializer.validated_data)
        return Response(PreferenceMeResponseSerializer(instance=pref).data)


class PreferenceGameReactionUpdateView(APIView):
    """
    PATCH - 특정 게임에 대한 반응(좋아요/저장 등) 수정
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="게임 반응 정보 수정",
        description="특정 게임에 대해 '찜하기(is_saved)' 또는 '반응(like, dislike, neutral)'을 설정합니다.",
        request=PreferenceGameReactionUpdateSerializer,
        responses={
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
            200: PreferenceGameReactionResponseSerializer,
            400: OpenApiResponse(description="유효하지 않은 반응 값이거나 데이터가 누락되었습니다."),
            401: OpenApiResponse(description="인증이 필요합니다."),
            404: OpenApiResponse(description="해당 게임을 찾을 수 없습니다."),
        },
        tags=["preferences"],
    )
    def patch(self, request: Request, game_id: int) -> Response:
        serializer = PreferenceGameReactionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        affinity = update_game_interaction(user=cast(User, request.user), game_id=game_id, **serializer.validated_data)
        res_serializer = PreferenceGameReactionResponseSerializer(instance=affinity)

        return Response(res_serializer.data, status=status.HTTP_200_OK)


class SavedGamesView(APIView):
    """
    GET - 내가 찜한 게임 목록 조회
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="내가 찜한 게임 목록 조회",
        description="is_saved=True인 게임 목록을 last_interacted_at 내림차순으로 반환합니다.",
        responses={
            200: inline_serializer(
                name="PaginatedSavedGameResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": SavedGameSerializer(many=True),
                },
            ),
            401: OpenApiResponse(description="인증이 필요합니다."),
        },
        parameters=PAGINATION_PARAMS,
        tags=["preferences"],
    )
    def get(self, request: Request) -> Response:
        qs = get_saved_games(user=cast(User, request.user))
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        affinities = page if page is not None else list(qs)

        # IGDB에서 게임 정보 hydrate
        igdb_ids = [a.igdb_game_id for a in affinities]
        games_by_id = {g["id"]: g for g in igdb_cache.get_games_by_ids(igdb_ids)}

        results = []
        for a in affinities:
            game = games_by_id.get(a.igdb_game_id, {})
            results.append(
                {
                    "id": a.igdb_game_id,
                    "name": game.get("name", ""),
                    "slug": game.get("slug", ""),
                    "thumbnail_img_url": game.get("thumbnail_img_url", ""),
                    "rawg_rating": game.get("rawg_rating", 0),
                    "saved_at": a.last_interacted_at,
                }
            )

        serializer = SavedGameSerializer(results, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)


class GameAffinitiesView(APIView):
    """
    GET - 내 게임 취향 상태 목록 조회
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="내 게임 취향 상태 목록 조회",
        description="유저가 상호작용한 게임 목록을 preference_score 내림차순으로 반환합니다.",
        responses={
            200: inline_serializer(
                name="PaginatedGameAffinityResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": GameAffinitySerializer(many=True),
                },
            ),
            401: OpenApiResponse(description="인증이 필요합니다."),
        },
        parameters=PAGINATION_PARAMS,
        tags=["preferences"],
    )
    def get(self, request: Request) -> Response:
        qs = get_game_affinities(user=cast(User, request.user))
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        affinities = page if page is not None else list(qs)

        # IGDB에서 게임 정보 hydrate
        igdb_ids = [a.igdb_game_id for a in affinities]
        games_by_id = {g["id"]: g for g in igdb_cache.get_games_by_ids(igdb_ids)}

        results = []
        for a in affinities:
            game = games_by_id.get(a.igdb_game_id, {})
            results.append(
                {
                    "id": a.igdb_game_id,
                    "name": game.get("name", ""),
                    "is_saved": a.is_saved,
                    "like_state": a.like_state,
                    "preference_score": float(a.preference_score),
                    "last_interacted_at": a.last_interacted_at,
                }
            )

        serializer = GameAffinitySerializer(results, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)
