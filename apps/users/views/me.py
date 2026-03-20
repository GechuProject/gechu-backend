import uuid
from typing import Any, cast

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import ErrorDetail
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.users.models.user import User
from apps.users.serializers.auth import MessageResponseSerializer
from apps.users.serializers.me import (
    UserMeDeleteResponseSerializer,
    UserMeResponseSerializer,
    UserMeUpdateRequestSerializer,
    UserMeUpdateResponseSerializer,
    UserPasswordChangeRequestSerializer,
    UserPasswordVerifyRequestSerializer,
    UserProfileImageResponseSerializer,
    UserProfileImageUploadRequestSerializer,
)
from apps.users.services import (
    change_user_password,
    delete_user_me,
    delete_user_profile_image,
    get_profile_image_content,
    get_user_me,
    update_user_me,
    upload_user_profile_image,
    verify_user_password,
)


@extend_schema(tags=["Users"])
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
        responses={200: UserMeResponseSerializer},
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="내 정보 수정",
        request=UserMeUpdateRequestSerializer,
        responses={200: UserMeUpdateResponseSerializer},
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
        responses={200: UserMeDeleteResponseSerializer},
    )
    def delete(self, request: Request, *args: object, **kwargs: object) -> Response:
        delete_user_me(self.get_object())
        result: dict[str, object] = {"message": "계정이 삭제되었습니다."}
        response_serializer = UserMeDeleteResponseSerializer(result)
        return Response(response_serializer.data)


@extend_schema(
    summary="비밀번호 확인",
    request=UserPasswordVerifyRequestSerializer,
    responses={200: MessageResponseSerializer},
    tags=["Users"],
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


@extend_schema(
    summary="비밀번호 변경",
    request=UserPasswordChangeRequestSerializer,
    responses={200: MessageResponseSerializer},
    tags=["Users"],
)
class UserPasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request) -> Response:
        serializer = UserPasswordChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        change_user_password(
            cast(User, request.user),
            new_password=cast(str, serializer.validated_data["new_password"]),
        )
        return Response(MessageResponseSerializer({"message": "비밀번호가 변경되었습니다."}).data)


class UserProfileImageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="프로필 이미지 업로드",
        description=(
            "프로필 이미지를 서버에 업로드합니다.\n\n"
            "- 허용 형식: jpg, jpeg, png, webp\n"
            "- 최대 파일 크기: 5MB\n"
            "- 이미지는 서버에서 자동으로 512×512 이하로 리사이즈되며, WebP 형식으로 변환되어 저장됩니다.\n"
            "- 기존 프로필 이미지가 있을 경우 자동으로 삭제됩니다."
        ),
        request={"multipart/form-data": UserProfileImageUploadRequestSerializer},
        responses={
            200: UserProfileImageResponseSerializer,
            400: OpenApiResponse(description="허용되지 않는 파일 형식이거나 파일 크기가 5MB를 초과한 경우"),
            401: OpenApiResponse(description="인증되지 않은 사용자"),
            404: OpenApiResponse(description="탈퇴한 사용자"),
        },
        tags=["Users"],
    )
    def put(self, request: Request) -> Response:
        serializer = UserProfileImageUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = upload_user_profile_image(
            cast(User, request.user),
            image_file=serializer.validated_data["image"],
            base_url=request.build_absolute_uri("/"),
        )
        return Response(UserProfileImageResponseSerializer(result).data)

    @extend_schema(
        summary="프로필 이미지 삭제",
        description=(
            "현재 프로필 이미지를 삭제합니다.\n\n"
            "- 삭제 후 `profile_img_url`은 `null`로 반환됩니다.\n"
            "- 이미 이미지가 없는 경우에도 정상 응답합니다."
        ),
        request=None,
        responses={
            200: UserProfileImageResponseSerializer,
            401: OpenApiResponse(description="인증되지 않은 사용자"),
            404: OpenApiResponse(description="탈퇴한 사용자"),
        },
        tags=["Users"],
    )
    def delete(self, request: Request) -> Response:
        result = delete_user_profile_image(cast(User, request.user))
        return Response(UserProfileImageResponseSerializer(result).data)


class UserProfileImageContentAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="프로필 이미지 조회",
        request=None,
        responses={
            200: OpenApiResponse(description="Compressed profile image"),
            404: OpenApiResponse(description="프로필 이미지가 없거나 사용자를 찾을 수 없는 경우"),
        },
        tags=["Users"],
    )
    def get(self, request: Request, public_id: uuid.UUID) -> HttpResponse:
        try:
            profile_image = get_profile_image_content(public_id=public_id)
        except CustomAPIException as exc:
            detail = exc.detail
            code = detail.get("code") if isinstance(detail, dict) else None
            if not isinstance(code, (str, ErrorDetail)) or str(code) != ErrorMessages.USER_NOT_FOUND.name:
                raise
            return HttpResponse(status=404)

        return HttpResponse(bytes(profile_image.image_data), content_type=profile_image.content_type)
