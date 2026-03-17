from typing import Any

from rest_framework import serializers


class PlatformResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    icon_url = serializers.CharField(allow_null=True)


class PlatformListResponseSerializer(serializers.Serializer[Any]):
    results = PlatformResponseSerializer(many=True)
