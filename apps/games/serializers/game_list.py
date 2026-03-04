from rest_framework import serializers

from apps.games.models.game import Game
from apps.games.models.genre import Genre
from apps.games.models.platform import Platform


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ["id", "name"]


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ["id", "name"]


class GameListSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    platforms = PlatformSerializer(many=True, read_only=True)

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
        ]