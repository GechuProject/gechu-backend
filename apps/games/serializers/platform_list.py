from typing import Any

from rest_framework import serializers

from apps.games.models import Platform


class PlatformResponseSerializer(serializers.ModelSerializer[Platform]):
    class Meta:
        model = Platform
        fields = [
            "id",
            "name",
            "slug",
            "icon_url",
        ]


class PlatformListResponseSerializer(serializers.Serializer[Any]):
    results = PlatformResponseSerializer(many=True)
