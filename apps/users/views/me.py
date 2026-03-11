from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.users.models.user import User
from apps.users.serializers.me import (
    UserMeResponseSerializer,
    UserMeUpdateRequestSerializer,
    UserMeUpdateResponseSerializer,
)
from apps.users.services import get_user_me, update_user_me


@extend_schema(tags=["Users"])
class UserMeAPIView(generics.RetrieveUpdateAPIView[User]):
    permission_classes = [IsAuthenticated]
    serializer_class = UserMeResponseSerializer
    http_method_names = ["get", "patch"]

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
