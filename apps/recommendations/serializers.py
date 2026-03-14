from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.recommendations.models import UserRecommendation


class RecommendationQuerySerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.CharField(required=False)
    genre = serializers.CharField(required=False)
    tag = serializers.CharField(required=False)
    is_free = serializers.BooleanField(required=False)
    is_adult = serializers.BooleanField(required=False)

    def validate_type(self, value: str) -> str:
        allowed = {choice for choice, _ in UserRecommendation.ReasonType.choices}
        if value not in allowed:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value

    def validate_genre(self, value: str | None) -> list[int]:
        return self._parse_int_list(value)

    def validate_tag(self, value: str | None) -> list[int]:
        return self._parse_int_list(value)

    def _parse_int_list(self, value: str | None) -> list[int]:
        if not value:
            return []
        try:
            return [int(x) for x in value.split(",") if x]
        except ValueError:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM) from None


class RecommendationGenreSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    name = serializers.CharField()


class RecommendationItemSerializer(serializers.ModelSerializer[UserRecommendation]):
    game_id = serializers.IntegerField(source="game.id")
    name = serializers.CharField(source="game.name")
    thumbnail_img_url = serializers.CharField(source="game.thumbnail_img_url")
    rawg_rating = serializers.DecimalField(source="game.rawg_rating", max_digits=3, decimal_places=2)
    tags = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()

    class Meta:
        model = UserRecommendation
        fields = [
            "game_id",
            "name",
            "reason",
            "generated_at",
            "rank",
            "score",
            "tags",
            "thumbnail_img_url",
            "rawg_rating",
            "genres",
        ]

    def get_tags(self, obj: UserRecommendation) -> list[str]:
        return [gt.tag.name for gt in obj.game.game_tags.all()]

    def get_genres(self, obj: UserRecommendation) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            RecommendationGenreSerializer(
                [{"id": gg.genre.id, "name": gg.genre.name} for gg in obj.game.game_genres.all()],
                many=True,
            ).data,
        )


class RecommendationListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = RecommendationItemSerializer(many=True)


class RecommendationStatusResponseSerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.ChoiceField(choices=["pending", "success", "failed"])
    generation = serializers.IntegerField(allow_null=True)
    generated_at = serializers.DateTimeField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)
