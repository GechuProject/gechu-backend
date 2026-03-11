from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.interactions.models import InteractionLog


class InteractionViewLogRequestSerializer(serializers.Serializer[dict[str, Any]]):
    game_id = serializers.IntegerField(min_value=1, required=False)
    source = serializers.CharField(required=False)  # type: ignore[assignment]
    metadata = serializers.JSONField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("game_id") is None or attrs.get("source") is None:
            raise CustomAPIException(ErrorMessages.GAME_ID_OR_SOURCE_MISSING)
        return attrs

    def validate_source(self, value: str) -> str:
        valid_sources = {choice for choice, _ in InteractionLog.SourceType.choices}
        if value not in valid_sources:
            raise CustomAPIException(ErrorMessages.INVALID_SOURCE)
        return value


class InteractionViewLogResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.IntegerField()
    type = serializers.CharField()
    logged_at = serializers.DateTimeField(source="created_at")
