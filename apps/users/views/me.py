from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models.user import User
from apps.users.serializers.auth import MessageResponseSerializer
from apps.users.serializers.me import (
    UserMeDeleteResponseSerializer,
    UserMeResponseSerializer,
    UserMeUpdateRequestSerializer,
    UserMeUpdateResponseSerializer,
    UserPasswordChangeRequestSerializer,
    UserPasswordVerifyRequestSerializer,
)
from apps.users.services import (
    change_user_password,
    delete_user_me,
    get_user_me,
    update_user_me,
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
