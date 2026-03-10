from typing import Any

from rest_framework import serializers

from apps.games.models import Genre


class GenreResponseSerializer(serializers.ModelSerializer[Genre]):
    class Meta:
        model = Genre
        fields = ["id", "name", "slug"]


class GenreListResponseSerializer(serializers.Serializer[Any]):
    results = GenreResponseSerializer(many=True)
