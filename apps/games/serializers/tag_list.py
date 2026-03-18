from rest_framework import serializers

from apps.games.models import Tag


class TagResponseSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class TagListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    results = TagResponseSerializer(many=True)


class TagListQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    search = serializers.CharField(required=False)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=50)
