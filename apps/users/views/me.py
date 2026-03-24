from typing import Any, cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers.error_serializer import ErrorResponseSerializer
from apps.users.models.user import User
from apps.users.serializers.auth import MessageResponseSerializer
from apps.users.serializers.me import (
    UserMeDeleteResponseSerializer,
    UserMeResponseSerializer,
    UserMeUpdateRequestSerializer,
    UserMeUpdateResponseSerializer,
    UserPasswordVerifyRequestSerializer,
    UserProfileImageResponseSerializer,
    UserProfileImageUploadRequestSerializer,
)
from apps.users.services import (
    delete_user_me,
    delete_user_profile_image,
    get_user_me,
    update_user_me,
    upload_user_profile_image,
    verify_user_password,
)

COOKIE_AUTH_DESCRIPTION = "HttpOnly access_token 쿠키 인증이 필요합니다."
UNSAFE_COOKIE_AUTH_DESCRIPTION = (
    "HttpOnly access_token 쿠키 인증이 필요합니다. "
    "POST, PUT, PATCH, DELETE 요청에는 X-CSRFToken 헤더도 함께 포함해야 합니다."
)


@extend_schema(tags=["users"])
class UserMeAPIView(generics.RetrieveUpdateDestroyAPIView[User]):
    permission_classes = [IsAuthenticated]
    serializer_class = UserMeResponseSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_object(self) -> User:
        return get_user_me(cast(User, self.request.user))

    def get_serializer_class(self) -> type[serializers.Serializer[Any]]:
        if self.request.method == "PATCH":
            return UserMeUpdateRequestSerializer
        return UserMeResponseSerializer

    @extend_schema(
        summary="내 정보 조회",
        description=COOKIE_AUTH_DESCRIPTION,
        responses={
            200: UserMeResponseSerializer,
            401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
        },
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="내 정보 수정",
        description=UNSAFE_COOKIE_AUTH_DESCRIPTION,
        request=UserMeUpdateRequestSerializer,
        responses={
            200: UserMeUpdateResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer, description="VALIDATION_ERROR, SOCIAL_USER_ONLY"),
            401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
            409: OpenApiResponse(response=ErrorResponseSerializer, description="NICKNAME_ALREADY_EXISTS"),
        },
    )
    def patch(self, request: Request, *args: object, **kwargs: object) -> Response:
        return self.update(request, *args, **kwargs)

    def update(self, request: Request, *args: object, **kwargs: object) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = update_user_me(instance, **serializer.validated_data)
        response_serializer = UserMeUpdateResponseSerializer(updated_user)
        return Response(response_serializer.data)

    @extend_schema(
        summary="회원 탈퇴",
        description=UNSAFE_COOKIE_AUTH_DESCRIPTION,
        responses={
            200: UserMeDeleteResponseSerializer,
            401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
        },
    )
    def delete(self, request: Request, *args: object, **kwargs: object) -> Response:
        delete_user_me(self.get_object())
        result: dict[str, object] = {"message": "계정이 삭제되었습니다."}
        response_serializer = UserMeDeleteResponseSerializer(result)
        return Response(response_serializer.data)


@extend_schema(
    summary="비밀번호 확인",
    description=UNSAFE_COOKIE_AUTH_DESCRIPTION,
    request=UserPasswordVerifyRequestSerializer,
    responses={
        200: MessageResponseSerializer,
        400: OpenApiResponse(response=ErrorResponseSerializer, description="SOCIAL_USER_ONLY"),
        401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
        403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
    },
    tags=["users"],
)
class UserPasswordVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = UserPasswordVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        verify_user_password(
            cast(User, request.user),
            password=cast(str, serializer.validated_data["password"]),
        )
        return Response(MessageResponseSerializer({"message": "비밀번호가 확인되었습니다."}).data)


class UserProfileImageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="프로필 이미지 업로드",
        description=(
            "프로필 이미지를 업로드합니다.\n\n"
            "- 지원 형식: jpg, jpeg, png, webp\n"
            "- 최대 파일 크기: 5MB\n"
            "- 서버에서 이미지를 512x512 이내로 리사이즈한 뒤 WebP로 저장합니다.\n"
            "- 기존 프로필 이미지는 자동으로 삭제됩니다."
        ),
        request={"multipart/form-data": UserProfileImageUploadRequestSerializer},
        responses={
            200: UserProfileImageResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer, description="INVALID_FILE_TYPE, FILE_TOO_LARGE"),
            401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
        },
        tags=["users"],
    )
    def put(self, request: Request) -> Response:
        serializer = UserProfileImageUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = upload_user_profile_image(
            cast(User, request.user),
            image_file=serializer.validated_data["image"],
        )
        return Response(UserProfileImageResponseSerializer(result).data)

    @extend_schema(
        summary="프로필 이미지 삭제",
        description=(
            "현재 프로필 이미지를 삭제합니다.\n\n"
            "- 삭제 후에는 profile_img_url이 null로 반환됩니다.\n"
            "- 등록된 이미지가 없어도 요청은 성공합니다."
        ),
        request=None,
        responses={
            200: UserProfileImageResponseSerializer,
            401: OpenApiResponse(response=ErrorResponseSerializer, description="UNAUTHORIZED, ACCOUNT_DEACTIVATED"),
            403: OpenApiResponse(response=ErrorResponseSerializer, description="CSRF_FAILED"),
        },
        tags=["users"],
    )
    def delete(self, request: Request) -> Response:
        result = delete_user_profile_image(cast(User, request.user))
        return Response(UserProfileImageResponseSerializer(result).data)
