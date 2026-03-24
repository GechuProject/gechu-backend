from __future__ import annotations

from typing import cast

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.models.user import User
from apps.users.serializers.search_recent import (
    RecentSearchDeleteResponseSerializer,
    RecentSearchListResponseSerializer,
)
from apps.users.services.search_recent_service import (
    clear_recent_searches,
    delete_recent_search_keyword,
    get_recent_searches,
)


@extend_schema(tags=["users"])
class RecentSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="최근 검색어 조회",
        responses={
            200: RecentSearchListResponseSerializer,
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        result = get_recent_searches(user=cast(User, request.user))
        return Response(RecentSearchListResponseSerializer(result).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="최근 검색어 전체 삭제",
        description=(
            "HttpOnly access_token cookie authentication is required. "
            "Unsafe requests must also include the X-CSRFToken header."
        ),
        responses={
            200: RecentSearchDeleteResponseSerializer,
            401: ErrorResponseSerializer,
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
        },
    )
    def delete(self, request: Request) -> Response:
        result = clear_recent_searches(user=cast(User, request.user))
        return Response(RecentSearchDeleteResponseSerializer(result).data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["users"],
    summary="최근 검색어 개별 삭제",
    parameters=[
        OpenApiParameter(
            name="keyword",
            type=str,
            location=OpenApiParameter.PATH,
            required=True,
            description="삭제할 검색어",
        )
    ],
    description=(
        "HttpOnly access_token cookie authentication is required. "
        "Unsafe requests must also include the X-CSRFToken header."
    ),
    responses={
        200: RecentSearchDeleteResponseSerializer,
        401: ErrorResponseSerializer,
        403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="해당 검색어를 찾을 수 없습니다.",
        ),
    },
)
class RecentSearchKeywordDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, keyword: str) -> Response:
        result = delete_recent_search_keyword(user=cast(User, request.user), keyword=keyword)
        return Response(RecentSearchDeleteResponseSerializer(result).data, status=status.HTTP_200_OK)
