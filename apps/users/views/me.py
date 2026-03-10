from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
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
        user = cast(User, self.request.user)
        if user.deleted_at is not None:
            raise CustomAPIException(ErrorMessages.USER_NOT_FOUND)
        return user
