from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.recommendations.models import RecommendationJob, UserRecommendation
from apps.users.models import User


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


class RecommendationGameSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """추천 응답 내 game 중첩 객체"""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    thumbnail_img_url = serializers.CharField()
    rawg_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    genres = serializers.ListField(child=serializers.DictField())


class RecommendationItemSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """IGDB에서 hydrate된 추천 항목"""

    rank = serializers.IntegerField()
    score = serializers.DecimalField(max_digits=5, decimal_places=4)
    reason = serializers.CharField()
    game = RecommendationGameSerializer()


class RecommendationListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = RecommendationItemSerializer(many=True)


class RecommendationStatusResponseSerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.ChoiceField(choices=["pending", "running", "success", "failed"])
    generation_version = serializers.IntegerField(allow_null=True)
    generated_at = serializers.DateTimeField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)


class RecommendationJobListQuerySerializer(serializers.Serializer[dict[str, Any]]):
    status = serializers.CharField(required=False)
    type = serializers.CharField(required=False)

    def validate_status(self, value: str) -> str:
        allowed = {"pending", "running", "success", "failed"}
        if value not in allowed:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value

    def validate_type(self, value: str) -> str:
        allowed = {"user_refresh", "similarity_rebuild"}
        if value not in allowed:
            raise CustomAPIException(ErrorMessages.INVALID_QUERY_PARAM)
        return value


class RecommendationJobItemSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.IntegerField()
    type = serializers.CharField(source="job_type")
    status = serializers.CharField()
    target_user = serializers.IntegerField(source="target_user_id", allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class RecommendationJobListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = RecommendationJobItemSerializer(many=True)


class RecommendationJobDetailResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    type = serializers.CharField(source="job_type")
    status = serializers.CharField()
    target_user = serializers.IntegerField(source="target_user_id", allow_null=True)
    error_message = serializers.CharField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class RecommendationJobRunRequestSerializer(serializers.Serializer[dict[str, Any]]):
    job_type = serializers.CharField(required=False)
    target_user = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        job_type = attrs.get("job_type")
        if not job_type:
            raise CustomAPIException(ErrorMessages.JOB_TYPE_MISSING)

        if job_type not in set(RecommendationJob.JobType.values):
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR)

        target_user = attrs.get("target_user")
        if target_user is not None and not User.objects.filter(id=target_user).exists():
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR)

        if job_type == RecommendationJob.JobType.SIMILARITY_REBUILD and target_user is not None:
            raise CustomAPIException(ErrorMessages.VALIDATION_ERROR)

        return attrs


class RecommendationJobRunResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    type = serializers.CharField(source="job_type")
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class AdminUserRecommendationItemSerializer(serializers.Serializer):  # type: ignore[type-arg]
    game_id = serializers.IntegerField(source="igdb_game_id")
    score = serializers.FloatField()


class AdminUserRecommendationListResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminUserRecommendationItemSerializer(many=True)
