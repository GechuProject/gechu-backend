from rest_framework import serializers

from apps.games.models import Game, GameGenre, GameMedia, GamePlatform, GameStore, GameTag


class GameGenreSerializer(serializers.ModelSerializer[GameGenre]):
    id = serializers.IntegerField(source="genre.id")
    name = serializers.CharField(source="genre.name")
    slug = serializers.CharField(source="genre.slug")

    class Meta:
        model = GameGenre
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


class GameTagSerializer(serializers.ModelSerializer[GameTag]):
    id = serializers.IntegerField(source="tag.id")
    name = serializers.CharField(source="tag.name")

    class Meta:
        model = GameTag
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
    genres = GameGenreSerializer(source="game_genres", many=True)
    tags = GameTagSerializer(source="game_tags", many=True)
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
