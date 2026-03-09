from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.users.models.user import User
from apps.users.serializers.me import UserMeResponseSerializer


@extend_schema(
    tags=["Users"],
    summary="내 정보 조회",
    responses={200: UserMeResponseSerializer},
)
class UserMeRetrieveAPIView(generics.RetrieveAPIView[User]):
    permission_classes = [IsAuthenticated]
    serializer_class = UserMeResponseSerializer

    def get_object(self) -> User:
        return cast(User, self.request.user)
