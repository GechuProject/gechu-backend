from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.preferences.models import UserPreference, UserPreferenceGenre, UserPreferencePlatform
from apps.preferences.serializers import (
    PreferenceGenresUpdateSerializer,
    PreferenceMeResponseSerializer,
    PreferencePlatformsUpdateSerializer,
)


class PreferenceMeRetrieveView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = PreferenceMeResponseSerializer(request.user)
        return Response(serializer.data)


class PreferenceMeGenresUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        req_serializer = PreferenceGenresUpdateSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        genre_ids: list[int] = req_serializer.validated_data["genre_ids"]

        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        UserPreferenceGenre.objects.filter(user_preference=pref).delete()
        for gid in genre_ids:
            UserPreferenceGenre.objects.create(user_preference=pref, genre_id=gid)

        response_serializer = PreferenceMeResponseSerializer(request.user)
        return Response(response_serializer.data)


@extend_schema(tags=["Preferences"])
class PreferenceMePlatformsUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        req_serializer = PreferencePlatformsUpdateSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        platform_ids: list[int] = req_serializer.validated_data["platform_ids"]

        pref, _ = UserPreference.objects.get_or_create(user=request.user)
        UserPreferencePlatform.objects.filter(user_preference=pref).delete()
        for pid in platform_ids:
            UserPreferencePlatform.objects.create(user_preference=pref, platform_id=pid)

        response_serializer = PreferenceMeResponseSerializer(request.user)
        return Response(response_serializer.data)
