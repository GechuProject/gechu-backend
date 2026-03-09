from typing import Any

from rest_framework import serializers


class SimilarGameQueryParamsSerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, default=10, min_value=1)


class SimilarGameResponseSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    thumbnail_img_url = serializers.URLField()
    rawg_rating = serializers.FloatField()
    similarity_score = serializers.FloatField(source="score")
