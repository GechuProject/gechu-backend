from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.interactions.serializers import (
    InteractionSearchLogRequestSerializer,
    InteractionSearchLogResponseSerializer,
    InteractionStoreClickLogRequestSerializer,
    InteractionStoreClickLogResponseSerializer,
    InteractionViewLogRequestSerializer,
    InteractionViewLogResponseSerializer,
)
from apps.interactions.services import (
    record_search_interaction,
    record_store_click_interaction,
    record_view_interaction,
)
from apps.users.models import User


@extend_schema(
    tags=["interactions"],
    summary="게임 조회 행동 기록",
    description=(
        "게임 조회(view) 행동을 기록합니다.\n\n"
        "- 최초 기록 시: `201`\n"
        "- 동일 source에서 쿨다운 내 중복 요청 시: 로그를 추가 생성하지 않고 `200`으로 기존 최근 로그를 반환합니다.\n"
        "- 가중치는 `interaction_weight_rules`(type=view)와 "
        "`interaction_context_rules`(source) 조합으로 계산됩니다."
    ),
    request=InteractionViewLogRequestSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "game_id": 1,
                "source": "recommendation",
                "metadata": {"page": 1, "section": "home_reco"},
            },
            request_only=True,
        ),
        OpenApiExample(
            "생성 응답 예시 (201)",
            value={
                "id": 101,
                "type": "view",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["201"],
        ),
        OpenApiExample(
            "쿨다운 무시 응답 예시 (200)",
            value={
                "id": 101,
                "type": "view",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
    responses={
        200: InteractionViewLogResponseSerializer,
        201: InteractionViewLogResponseSerializer,
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="CSRF_FAILED",
        ),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="잘못된 요청입니다.",
            examples=[
                OpenApiExample(
                    "필수값 누락",
                    value={
                        "status_code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.status_code,
                        "code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.name,
                        "message": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "source 값 오류",
                    value={
                        "status_code": ErrorMessages.INVALID_SOURCE.status_code,
                        "code": ErrorMessages.INVALID_SOURCE.name,
                        "message": ErrorMessages.INVALID_SOURCE.message,
                    },
                ),
            ],
        ),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="인증이 필요합니다.",
            examples=[
                OpenApiExample(
                    "인증 필요",
                    value={
                        "status_code": ErrorMessages.UNAUTHORIZED.status_code,
                        "code": ErrorMessages.UNAUTHORIZED.name,
                        "message": ErrorMessages.UNAUTHORIZED.message,
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="대상을 찾을 수 없습니다.",
            examples=[
                OpenApiExample(
                    "게임 없음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "view 룰 없음",
                    value={
                        "status_code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.status_code,
                        "code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.name,
                        "message": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "source 룰 없음",
                    value={
                        "status_code": ErrorMessages.SOURCE_NOT_FOUND.status_code,
                        "code": ErrorMessages.SOURCE_NOT_FOUND.name,
                        "message": ErrorMessages.SOURCE_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class InteractionViewLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InteractionViewLogRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = cast(User, request.user)
        log, created = record_view_interaction(
            user=user,
            game_id=data["game_id"],
            source=data["source"],
            metadata=data.get("metadata"),
        )

        response_serializer = InteractionViewLogResponseSerializer(log)
        return Response(response_serializer.data, status=201 if created else 200)


@extend_schema(
    tags=["interactions"],
    summary="게임 검색 행동 기록",
    description=(
        "게임 검색(search) 행동을 기록합니다.\n\n"
        "- 이 API는 **게임이 선택된 검색 행동만** 기록하므로 `game_id`가 필수입니다.\n"
        "- 최초 기록 시: `201`\n"
        "- 동일 검색어/동일 game/source에서 쿨다운 내 중복 요청 시: 로그를 추가 생성하지 않고 `200`으로 기존 최근 로그를 반환합니다.\n"
        "- 가중치는 `interaction_weight_rules`(type=search)와 "
        "`interaction_context_rules`(source=search_result) 조합으로 계산됩니다."
    ),
    request=InteractionSearchLogRequestSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "game_id": 1,
                "search_query": "elden ring",
                "source": "search_result",
                "metadata": {"result_rank": 2, "keyword_length": 10},
            },
            request_only=True,
        ),
        OpenApiExample(
            "생성 응답 예시 (201)",
            value={
                "id": 201,
                "type": "search",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["201"],
        ),
        OpenApiExample(
            "쿨다운 무시 응답 예시 (200)",
            value={
                "id": 201,
                "type": "search",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
    responses={
        200: InteractionSearchLogResponseSerializer,
        201: InteractionSearchLogResponseSerializer,
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="CSRF_FAILED",
        ),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="잘못된 요청입니다.",
            examples=[
                OpenApiExample(
                    "search_query 누락",
                    value={
                        "status_code": ErrorMessages.SEARCH_QUERY_MISSING.status_code,
                        "code": ErrorMessages.SEARCH_QUERY_MISSING.name,
                        "message": ErrorMessages.SEARCH_QUERY_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "game_id/source 누락",
                    value={
                        "status_code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.status_code,
                        "code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.name,
                        "message": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "source 값 오류",
                    value={
                        "status_code": ErrorMessages.INVALID_SOURCE.status_code,
                        "code": ErrorMessages.INVALID_SOURCE.name,
                        "message": ErrorMessages.INVALID_SOURCE.message,
                    },
                ),
            ],
        ),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="인증이 필요합니다.",
            examples=[
                OpenApiExample(
                    "인증 필요",
                    value={
                        "status_code": ErrorMessages.UNAUTHORIZED.status_code,
                        "code": ErrorMessages.UNAUTHORIZED.name,
                        "message": ErrorMessages.UNAUTHORIZED.message,
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="대상을 찾을 수 없습니다.",
            examples=[
                OpenApiExample(
                    "게임 없음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "search 룰 없음",
                    value={
                        "status_code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.status_code,
                        "code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.name,
                        "message": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "source 룰 없음",
                    value={
                        "status_code": ErrorMessages.SOURCE_NOT_FOUND.status_code,
                        "code": ErrorMessages.SOURCE_NOT_FOUND.name,
                        "message": ErrorMessages.SOURCE_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class InteractionSearchLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InteractionSearchLogRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = cast(User, request.user)
        log, created = record_search_interaction(
            user=user,
            game_id=data["game_id"],
            search_query=data["search_query"],
            source=data["source"],
            metadata=data.get("metadata"),
        )

        response_serializer = InteractionSearchLogResponseSerializer(log)
        return Response(response_serializer.data, status=201 if created else 200)


@extend_schema(
    tags=["interactions"],
    summary="외부 스토어 이동 행동 기록",
    description=(
        "게임 상세 페이지에서 외부 스토어 이동(store_click) 행동을 기록합니다.\n\n"
        "- 이 API는 `source=detail_page`만 허용합니다.\n"
        "- 최초 기록 시: `201`\n"
        "- 동일 game/store/source에서 쿨다운 내 중복 요청 시: 로그를 추가 생성하지 않고 `200`으로 기존 최근 로그를 반환합니다.\n"
        "- 반복 감쇠(repeat_decay) 계산은 `user + game + store + type` 기준으로 적용됩니다.\n"
        "- 가중치는 `interaction_weight_rules`(type=store_click)와 "
        "`interaction_context_rules`(source=detail_page) 조합으로 계산됩니다."
    ),
    request=InteractionStoreClickLogRequestSerializer,
    examples=[
        OpenApiExample(
            "요청 예시",
            value={
                "game_id": 1,
                "store_id": 3,
                "source": "detail_page",
                "metadata": {"button_position": "hero", "cta_variant": "primary"},
            },
            request_only=True,
        ),
        OpenApiExample(
            "생성 응답 예시 (201)",
            value={
                "id": 301,
                "type": "store_click",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["201"],
        ),
        OpenApiExample(
            "쿨다운 무시 응답 예시 (200)",
            value={
                "id": 301,
                "type": "store_click",
                "logged_at": "2026-03-11T08:30:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
    responses={
        200: InteractionStoreClickLogResponseSerializer,
        201: InteractionStoreClickLogResponseSerializer,
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="CSRF_FAILED",
        ),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="잘못된 요청입니다.",
            examples=[
                OpenApiExample(
                    "game_id/store_id 누락",
                    value={
                        "status_code": ErrorMessages.GAME_ID_OR_STORE_ID_MISSING.status_code,
                        "code": ErrorMessages.GAME_ID_OR_STORE_ID_MISSING.name,
                        "message": ErrorMessages.GAME_ID_OR_STORE_ID_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "source 누락",
                    value={
                        "status_code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.status_code,
                        "code": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.name,
                        "message": ErrorMessages.GAME_ID_OR_SOURCE_MISSING.message,
                    },
                ),
                OpenApiExample(
                    "source 값 오류",
                    value={
                        "status_code": ErrorMessages.INVALID_SOURCE.status_code,
                        "code": ErrorMessages.INVALID_SOURCE.name,
                        "message": ErrorMessages.INVALID_SOURCE.message,
                    },
                ),
            ],
        ),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="인증이 필요합니다.",
            examples=[
                OpenApiExample(
                    "인증 필요",
                    value={
                        "status_code": ErrorMessages.UNAUTHORIZED.status_code,
                        "code": ErrorMessages.UNAUTHORIZED.name,
                        "message": ErrorMessages.UNAUTHORIZED.message,
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="대상을 찾을 수 없습니다.",
            examples=[
                OpenApiExample(
                    "게임 없음",
                    value={
                        "status_code": ErrorMessages.GAME_NOT_FOUND.status_code,
                        "code": ErrorMessages.GAME_NOT_FOUND.name,
                        "message": ErrorMessages.GAME_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "스토어 없음",
                    value={
                        "status_code": ErrorMessages.STORE_NOT_FOUND.status_code,
                        "code": ErrorMessages.STORE_NOT_FOUND.name,
                        "message": ErrorMessages.STORE_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "store_click 룰 없음",
                    value={
                        "status_code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.status_code,
                        "code": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.name,
                        "message": ErrorMessages.INTERACTION_TYPE_NOT_FOUND.message,
                    },
                ),
                OpenApiExample(
                    "source 룰 없음",
                    value={
                        "status_code": ErrorMessages.SOURCE_NOT_FOUND.status_code,
                        "code": ErrorMessages.SOURCE_NOT_FOUND.name,
                        "message": ErrorMessages.SOURCE_NOT_FOUND.message,
                    },
                ),
            ],
        ),
    },
)
class InteractionStoreClickLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = InteractionStoreClickLogRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = cast(User, request.user)
        log, created = record_store_click_interaction(
            user=user,
            game_id=data["game_id"],
            store_id=data["store_id"],
            source=data["source"],
            metadata=data.get("metadata"),
        )

        response_serializer = InteractionStoreClickLogResponseSerializer(log)
        return Response(response_serializer.data, status=201 if created else 200)
