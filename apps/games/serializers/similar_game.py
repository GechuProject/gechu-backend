from typing import Any

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages


class SimilarGameQueryParamsSerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, default=10)

    def validate_limit(self, value: int) -> int:
        if value < 1 or value > 30:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value


class SimilarGameResponseSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(source="similar_game.id")
    name = serializers.CharField(source="similar_game.name")
    slug = serializers.CharField(source="similar_game.slug")
    thumbnail_img_url = serializers.URLField(source="similar_game.thumbnail_img_url")
    rawg_rating = serializers.FloatField(source="similar_game.rawg_rating")
    similarity_score = serializers.FloatField(source="score")
