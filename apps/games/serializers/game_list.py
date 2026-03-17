from typing import Any

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages


# -----------------------
# 공통 Serializer
# -----------------------
class GenreSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PlatformSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()


# -----------------------
# 요청 Serializer
# -----------------------
class GameListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    search = serializers.CharField(required=False)
    ordering = serializers.CharField(default="-rawg_rating", required=False)
    genre_ids = serializers.CharField(required=False)
    platform_ids = serializers.CharField(required=False)
    tag_ids = serializers.CharField(required=False)
    page = serializers.IntegerField(default=1, required=False)
    page_size = serializers.IntegerField(default=20, required=False)

    def validate_ordering(self, value: str) -> str:
        allowed = ["rawg_rating", "-rawg_rating", "released", "-released", "rawg_added", "-rawg_added"]
        if value not in allowed:
            raise CustomAPIException(ErrorMessages.INVALID_ORDERING)
        return value

    def validate_genre_ids(self, value: str | None) -> list[int]:
        return self._parse_int_list(value)

    def validate_platform_ids(self, value: str | None) -> list[int]:
        return self._parse_int_list(value)

    def validate_tag_ids(self, value: str | None) -> list[int]:
        return self._parse_int_list(value)

    def validate_page_size(self, value: int) -> int:
        if value < 1 or value > 100:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value

    def _parse_int_list(self, value: str | None) -> list[int]:
        if not value:
            return []

        try:
            return [int(x) for x in value.split(",") if x]
        except ValueError:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM) from None


# -----------------------
# 응답 Serializer
# -----------------------
class GameListItemSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    released = serializers.DateField(allow_null=True)
    thumbnail_img_url = serializers.CharField()
    rawg_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    rawg_ratings_count = serializers.IntegerField()
    genres = GenreSerializer(many=True)
    platforms = PlatformSerializer(many=True)


class GameListResponseSerializer(serializers.Serializer[dict[str, Any]]):
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = GameListItemSerializer(many=True)
