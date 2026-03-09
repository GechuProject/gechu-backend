from typing import Any
from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages


class SimilarGameQueryParamsSerializer(serializers.Serializer[Any]):
    limit = serializers.IntegerField(required=False, default=10, min_value=1)

    def validate_limit(self, value: int) -> int:
        if value < 1:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value


class SimilarGameResponseSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    thumbnail_img_url = serializers.URLField()
    rawg_rating = serializers.FloatField()
    similarity_score = serializers.FloatField(source="score")
