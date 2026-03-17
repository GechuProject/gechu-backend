from typing import Any

from rest_framework import serializers


class GenreResponseSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class GenreListResponseSerializer(serializers.Serializer[Any]):
    results = GenreResponseSerializer(many=True)
