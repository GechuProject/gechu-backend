from __future__ import annotations

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsStaffAdmin
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.users.models.user import User
from apps.users.serializers.admin_user import (
    AdminUserDetailResponseSerializer,
    AdminUserListItemSerializer,
    AdminUserListResponseSerializer,
    AdminUserStatusUpdateRequestSerializer,
)
from apps.users.services import get_admin_user, list_admin_users, update_admin_user_status


@extend_schema(
    tags=["admin"],
    summary="어드민 - 유저 목록 조회",
    parameters=PAGINATION_PARAMS,
    responses={
        200: AdminUserListResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
    },
)
class AdminUserListAPIView(ListAPIView):  # type: ignore[type-arg]
    permission_classes = [IsAuthenticated, IsStaffAdmin]
    serializer_class = AdminUserListItemSerializer
    pagination_class = Pagination

    def get_queryset(self) -> QuerySet[User]:
        return list_admin_users()


@extend_schema(
    tags=["admin"],
    summary="어드민 - 유저 상세 조회",
    responses={
        200: AdminUserDetailResponseSerializer,
        401: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
        404: OpenApiResponse(response=ErrorResponseSerializer, description="User not found"),
    },
)
class AdminUserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffAdmin]

    def get(self, request: Request, user_id: int) -> Response:
        user = get_admin_user(user_id=user_id)
        serializer = AdminUserDetailResponseSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["admin"],
        summary="어드민 - 유저 상태 변경",
        request=AdminUserStatusUpdateRequestSerializer,
        responses={
            200: AdminUserDetailResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, description="User not found"),
        },
    )
    def patch(self, request: Request, user_id: int) -> Response:
        serializer = AdminUserStatusUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = update_admin_user_status(
            user_id=user_id,
            is_active=bool(serializer.validated_data["is_active"]),
        )
        response_serializer = AdminUserDetailResponseSerializer(user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
