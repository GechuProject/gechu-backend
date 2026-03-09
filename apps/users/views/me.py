from typing import cast

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.users.models.user import User
from apps.users.serializers.me import UserMeResponseSerializer


class UserMeRetrieveAPIView(generics.RetrieveAPIView[User]):
    permission_classes = [IsAuthenticated]
    serializer_class = UserMeResponseSerializer

    def get_object(self) -> User:
        return cast(User, self.request.user)
