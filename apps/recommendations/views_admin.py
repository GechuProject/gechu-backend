from __future__ import annotations

from typing import cast

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.core.permissions import IsStaffAdmin
from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.core.utils.pagination import PAGINATION_PARAMS, Pagination
from apps.recommendations.models import RecommendationJob
from apps.recommendations.serializers import (
    AdminUserRecommendationItemSerializer,
    AdminUserRecommendationListResponseSerializer,
    RecommendationJobDetailResponseSerializer,
    RecommendationJobItemSerializer,
    RecommendationJobListQuerySerializer,
    RecommendationJobListResponseSerializer,
    RecommendationJobRunRequestSerializer,
    RecommendationJobRunResponseSerializer,
)
from apps.recommendations.services import RecommendationAdminService
from apps.recommendations.tasks import process_similarity_rebuild_job, process_user_refresh_job
from apps.users.models import User

COOKIE_AUTH_DESCRIPTION = "HttpOnly access_token cookie authentication is required."
UNSAFE_COOKIE_AUTH_DESCRIPTION = (
    "HttpOnly access_token cookie authentication is required. Unsafe requests must also include the X-CSRFToken header."
)


@extend_schema(
    tags=["admin"],
    summary="추천 작업 목록 조회",
    description="관리자 권한으로 추천 작업 목록을 조회합니다.",
    parameters=[
        OpenApiParameter(
            "status",
            type=str,
            required=False,
            description="작업 상태 필터",
            enum=["pending", "running", "success", "failed"],
        ),
        OpenApiParameter(
            "type",
            type=str,
            required=False,
            description="작업 유형 필터",
            enum=["user_refresh", "similarity_rebuild"],
        ),
        *PAGINATION_PARAMS,
    ],
    responses={
        200: RecommendationJobListResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description=COOKIE_AUTH_DESCRIPTION,
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
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Forbidden",
            examples=[
                OpenApiExample(
                    "관리자 권한 필요",
                    value={
                        "status_code": ErrorMessages.FORBIDDEN.status_code,
                        "code": ErrorMessages.FORBIDDEN.name,
                        "message": ErrorMessages.FORBIDDEN.message,
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "잘못된 쿼리 파라미터",
                    value={
                        "status_code": ErrorMessages.INVALID_QUERY_PARAM.status_code,
                        "code": ErrorMessages.INVALID_QUERY_PARAM.name,
                        "message": ErrorMessages.INVALID_QUERY_PARAM.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"status": "failed", "type": "user_refresh", "page": 1, "page_size": 20},
            request_only=True,
        ),
        OpenApiExample(
            "응답 예시",
            value={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": 15,
                        "type": "user_refresh",
                        "status": "success",
                        "target_user": 1,
                        "started_at": "2025-06-10T01:00:00Z",
                        "created_at": "2025-06-10T00:59:00Z",
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AdminRecommendationJobListView(ListAPIView):  # type: ignore[type-arg]
    permission_classes = [IsAuthenticated]
    serializer_class = RecommendationJobItemSerializer
    pagination_class = Pagination

    def get_queryset(self) -> QuerySet[RecommendationJob]:
        user = cast(User, self.request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        query_serializer = RecommendationJobListQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)
        data = query_serializer.validated_data

        return RecommendationAdminService.list_recommendation_jobs(
            job_status=cast(str | None, data.get("status")),
            job_type=cast(str | None, data.get("type")),
        )


@extend_schema(
    tags=["admin"],
    summary="추천 작업 상세 조회",
    description="관리자 권한으로 추천 작업 상세 정보를 조회합니다.",
    responses={
        200: RecommendationJobDetailResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description=COOKIE_AUTH_DESCRIPTION,
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
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Forbidden",
            examples=[
                OpenApiExample(
                    "관리자 권한 필요",
                    value={
                        "status_code": ErrorMessages.FORBIDDEN.status_code,
                        "code": ErrorMessages.FORBIDDEN.name,
                        "message": ErrorMessages.FORBIDDEN.message,
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Not Found",
            examples=[
                OpenApiExample(
                    "작업 없음",
                    value={
                        "status_code": ErrorMessages.JOB_NOT_FOUND.status_code,
                        "code": ErrorMessages.JOB_NOT_FOUND.name,
                        "message": ErrorMessages.JOB_NOT_FOUND.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "응답 예시",
            value={
                "id": 5,
                "type": "user_refresh",
                "status": "failed",
                "target_user": 2,
                "error_message": "Connection timeout",
                "started_at": "2025-06-10T01:00:00Z",
                "created_at": "2025-06-10T00:59:00Z",
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class AdminRecommendationJobDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, job_id: int) -> Response:
        user = cast(User, request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        job = RecommendationAdminService.get_recommendation_job(job_id=job_id)
        if job is None:
            raise CustomAPIException(ErrorMessages.JOB_NOT_FOUND)

        serializer = RecommendationJobDetailResponseSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["admin"],
    summary="추천 작업 수동 실행",
    description="관리자 권한으로 추천 작업을 수동 실행합니다.",
    request=RecommendationJobRunRequestSerializer,
    responses={
        201: RecommendationJobRunResponseSerializer,
        400: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Bad Request",
            examples=[
                OpenApiExample(
                    "job_type 누락",
                    value={
                        "status_code": ErrorMessages.JOB_TYPE_MISSING.status_code,
                        "code": ErrorMessages.JOB_TYPE_MISSING.name,
                        "message": ErrorMessages.JOB_TYPE_MISSING.message,
                    },
                )
            ],
        ),
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description=UNSAFE_COOKIE_AUTH_DESCRIPTION,
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
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="FORBIDDEN or CSRF_FAILED",
            examples=[
                OpenApiExample(
                    "관리자 권한 필요",
                    value={
                        "status_code": ErrorMessages.FORBIDDEN.status_code,
                        "code": ErrorMessages.FORBIDDEN.name,
                        "message": ErrorMessages.FORBIDDEN.message,
                    },
                )
            ],
        ),
        409: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="Conflict",
            examples=[
                OpenApiExample(
                    "이미 실행 중인 작업",
                    value={
                        "status_code": ErrorMessages.JOB_ALREADY_RUNNING.status_code,
                        "code": ErrorMessages.JOB_ALREADY_RUNNING.name,
                        "message": ErrorMessages.JOB_ALREADY_RUNNING.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "요청 예시",
            value={"job_type": "user_refresh", "target_user": None},
            request_only=True,
        ),
        OpenApiExample(
            "응답 예시",
            value={
                "id": 11,
                "type": "user_refresh",
                "status": "pending",
                "created_at": "2025-08-01T12:00:00Z",
            },
            response_only=True,
            status_codes=["201"],
        ),
    ],
)
class AdminRecommendationJobRunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        if not user.is_staff:
            raise CustomAPIException(ErrorMessages.FORBIDDEN)

        req_serializer = RecommendationJobRunRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        data = req_serializer.validated_data

        job = RecommendationAdminService.create_recommendation_job(
            job_type=cast(str, data["job_type"]),
            target_user_id=cast(int | None, data.get("target_user")),
        )
        if job.job_type == RecommendationJob.JobType.USER_REFRESH and job.target_user_id is not None:
            process_user_refresh_job.delay(job.id)
        elif job.job_type == RecommendationJob.JobType.SIMILARITY_REBUILD:
            process_similarity_rebuild_job.delay(job.id)

        serializer = RecommendationJobRunResponseSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["admin"],
    summary="어드민 - 특정 유저 추천 결과 조회",
    description=(
        "관리자(staff) 전용 API입니다. path의 유저 ID에 해당하는 추천 결과 목록을 페이지네이션으로 조회합니다. "
        "추천 디버깅용으로 사용합니다. 각 항목은 game_id(IGDB 게임 ID)와 score를 반환합니다."
    ),
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=int,
            location=OpenApiParameter.PATH,
            required=True,
            description="추천 결과를 조회할 유저의 ID (user pk)",
        ),
        *PAGINATION_PARAMS,
    ],
    responses={
        200: AdminUserRecommendationListResponseSerializer,
        401: OpenApiResponse(
            response=ErrorResponseSerializer,
            description=COOKIE_AUTH_DESCRIPTION,
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
        403: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="권한 없음. is_staff=True인 관리자만 호출할 수 있습니다.",
            examples=[
                OpenApiExample(
                    "관리자 권한 필요",
                    value={
                        "status_code": ErrorMessages.FORBIDDEN.status_code,
                        "code": ErrorMessages.FORBIDDEN.name,
                        "message": ErrorMessages.FORBIDDEN.message,
                    },
                )
            ],
        ),
        404: OpenApiResponse(
            response=ErrorResponseSerializer,
            description="해당 ID의 사용자를 찾을 수 없음.",
            examples=[
                OpenApiExample(
                    "USER_NOT_FOUND",
                    value={
                        "status_code": ErrorMessages.USER_NOT_FOUND.status_code,
                        "code": ErrorMessages.USER_NOT_FOUND.name,
                        "message": ErrorMessages.USER_NOT_FOUND.message,
                    },
                )
            ],
        ),
    },
    examples=[
        OpenApiExample(
            "성공 시 응답 예시",
            value={
                "count": 20,
                "next": "http://example.com/api/v1/admin/users/1/recommendations/?page=2",
                "previous": None,
                "results": [
                    {"game_id": 12345, "score": "120.5000"},
                    {"game_id": 67890, "score": "98.2000"},
                ],
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
)
class AdminUserRecommendationListView(APIView):
    permission_classes = [IsStaffAdmin]

    def get(self, request: Request, user_id: int) -> Response:
        if not User.objects.filter(pk=user_id).exists():
            raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)

        qs = RecommendationAdminService.list_user_recommendations(user_id=user_id)
        paginator = Pagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminUserRecommendationItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
