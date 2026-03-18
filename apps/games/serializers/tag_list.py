from rest_framework import serializers

from apps.games.models import Tag


class TagResponseSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class TagListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    results = TagResponseSerializer(many=True)