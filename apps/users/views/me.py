from typing import cast

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models.user import User
from apps.users.serializers.me import UserMeResponseSerializer


class UserMeRetrieveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = UserMeResponseSerializer(user)
        return Response(serializer.data)