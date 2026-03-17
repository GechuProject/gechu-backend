from typing import Any

from rest_framework import serializers


class GameGenreSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class GamePlatformSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()


class GameTagSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    name = serializers.CharField()


class GameMediaSerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.CharField()
    media_url = serializers.CharField()
    video_url_480 = serializers.CharField(allow_null=True)
    video_url_max = serializers.CharField(allow_null=True)


class GameStoreSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    url = serializers.CharField()


class GameDetailSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    released = serializers.DateField(allow_null=True)
    tba = serializers.BooleanField()
    thumbnail_img_url = serializers.CharField()
    website = serializers.CharField(allow_blank=True)
    rawg_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    rawg_ratings_count = serializers.IntegerField()
    rawg_added = serializers.IntegerField()
    esrb_rating = serializers.CharField()
    age_rating_min = serializers.IntegerField()
    genres = GameGenreSerializer(many=True)
    platforms = GamePlatformSerializer(many=True)
    tags = GameTagSerializer(many=True)
    media = GameMediaSerializer(many=True)
    stores = GameStoreSerializer(many=True)
