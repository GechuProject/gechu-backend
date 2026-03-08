from typing import Any

from rest_framework import serializers

from apps.games.models import Game, GameMedia, GamePlatform, GameStore, Genre, Tag


class GenreSerializer(serializers.ModelSerializer[Genre]):
    class Meta:
        model = Genre
        fields = ["id", "name", "slug"]


class GamePlatformSerializer(serializers.ModelSerializer[GamePlatform]):
    id = serializers.IntegerField(source="platform.id")
    name = serializers.CharField(source="platform.name")

    class Meta:
        model = GamePlatform
        fields = [
            "id",
            "name",
            "requirements_minimum",
            "requirements_recommended",
        ]


class TagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class GameMediaSerializer(serializers.ModelSerializer[GameMedia]):
    class Meta:
        model = GameMedia
        fields = [
            "type",
            "media_url",
            "video_url_480",
            "video_url_max",
        ]


class GameStoreSerializer(serializers.ModelSerializer[GameStore]):
    name = serializers.CharField(source="store.name")

    class Meta:
        model = GameStore
        fields = [
            "name",
            "url",
        ]


class GameDetailSerializer(serializers.ModelSerializer[Game]):
    genres = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    platforms = GamePlatformSerializer(source="game_platforms", many=True)
    media = GameMediaSerializer(many=True)
    stores = GameStoreSerializer(source="game_stores", many=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "released",
            "tba",
            "thumbnail_img_url",
            "website",
            "rawg_rating",
            "rawg_ratings_count",
            "metacritic",
            "rawg_added",
            "playtime",
            "esrb_rating",
            "age_rating_min",
            "genres",
            "platforms",
            "tags",
            "media",
            "stores",
        ]

    def get_genres(self, obj: Game) -> list[dict[str, Any]]:
        genres = [gg.genre for gg in obj.game_genres.all()]
        return GenreSerializer(genres, many=True).data  # type: ignore[return-value]

    def get_tags(self, obj: Game) -> list[dict[str, Any]]:
        tags = [gt.tag for gt in obj.game_tags.all()]
        return TagSerializer(tags, many=True).data  # type: ignore[return-value]
