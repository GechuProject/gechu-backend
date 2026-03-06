from typing import Any, cast

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models.catalog import Game
from apps.games.models.metadata import Genre, Platform, Tag


# -----------------------
# 공통 Serializer
# -----------------------
class GenreSerializer(serializers.ModelSerializer[Genre]):
    class Meta:
        model = Genre
        fields = ["id", "name"]


class PlatformSerializer(serializers.ModelSerializer[Platform]):
    class Meta:
        model = Platform
        fields = ["id", "name"]


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name"]


# -----------------------
# 요청 Serializer
# -----------------------
class GameListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    search = serializers.CharField(required=False)
    esrb_rating = serializers.CharField(required=False)
    ordering = serializers.CharField(default="-rawg_rating", required=False)
    genre_ids = serializers.CharField(required=False)
    platform_ids = serializers.CharField(required=False)
    tag_ids = serializers.CharField(required=False)

    def validate_esrb_rating(self, value: str) -> str:
        allowed = ["everyone", "everyone_10_plus", "teen", "mature", "adults_only", "rating_pending", "unknown"]
        if value not in allowed:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value

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
class GameListResponseSerializer(serializers.ModelSerializer["Game"]):
    genres = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id",
            "slug",
            "name",
            "released",
            "thumbnail_img_url",
            "rawg_rating",
            "rawg_ratings_count",
            "metacritic",
            "genres",
            "platforms",
            "tags",
        ]

    def get_genres(self, obj: Game) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], GenreSerializer([gg.genre for gg in obj.game_genres.all()], many=True).data)

    def get_platforms(self, obj: Game) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]], PlatformSerializer([gp.platform for gp in obj.game_platforms.all()], many=True).data
        )

    def get_tags(self, obj: Game) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], TagSerializer([gt.tag for gt in obj.game_tags.all()], many=True).data)
