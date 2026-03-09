from rest_framework import serializers


class SimilarGameListQueryParamsSerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False,
        default=10,
        min_value=1,
        help_text="조회할 유사 게임 개수 (기본값 10)"
    )


class SimilarGameSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    slug = serializers.CharField(max_length=255)
    thumbnail_img_url = serializers.URLField()
    rawg_rating = serializers.FloatField()
    similarity_score = serializers.FloatField()
