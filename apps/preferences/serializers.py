from typing import Any

from rest_framework import serializers

from apps.core.exceptions.exception_handler import CustomAPIException
from apps.core.exceptions.exception_message import ErrorMessages
from apps.games.models import Genre, Platform, Tag
from apps.interactions.models import InteractionLog
from apps.preferences.models import UserGameAffinity, UserPreference


class PreferenceMeResponseSerializer(serializers.Serializer[UserPreference]):
    genres = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_genres(self, obj: UserPreference) -> list[dict[str, int | str]]:
        return [
            {"id": i.genre.id, "name": i.genre.name} for i in obj.userpreferencegenre_set.select_related("genre").all()
        ]

    def get_platforms(self, obj: UserPreference) -> list[dict[str, int | str]]:
        return [
            {"id": i.platform.id, "name": i.platform.name}
            for i in obj.userpreferenceplatform_set.select_related("platform").all()
        ]

    def get_tags(self, obj: UserPreference) -> list[dict[str, int | str]]:
        return [{"id": i.tag.id, "name": i.tag.name} for i in obj.userpreferencetag_set.select_related("tag").all()]


class PreferenceUpdateSerializer(serializers.Serializer[None]):
    genre_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    platform_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    tag_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        required_fields = ["genre_ids", "platform_ids", "tag_ids"]

        for field in required_fields:
            if field not in self.initial_data:
                raise CustomAPIException(ErrorMessages.PREFERENCE_FIELDS_REQUIRED)

        return attrs

    def validate_genre_ids(self, value: list[int]) -> list[int]:
        existing_ids = set(Genre.objects.filter(id__in=value).values_list("id", flat=True))
        if existing_ids != set(value):
            raise CustomAPIException(ErrorMessages.INVALID_GENRE_ID)
        return value

    def validate_platform_ids(self, value: list[int]) -> list[int]:
        existing_ids = set(Platform.objects.filter(id__in=value).values_list("id", flat=True))
        if existing_ids != set(value):
            raise CustomAPIException(ErrorMessages.INVALID_PLATFORM_ID)
        return value

    def validate_tag_ids(self, value: list[int]) -> list[int]:
        existing_ids = set(Tag.objects.filter(id__in=value).values_list("id", flat=True))
        if existing_ids != set(value):
            raise CustomAPIException(ErrorMessages.INVALID_TAG_ID)
        return value


REACTION_CHOICES = ("like", "dislike", "neutral")


class PreferenceGameReactionUpdateSerializer(serializers.Serializer[None]):
    is_saved = serializers.BooleanField(required=False)
    reaction = serializers.CharField(required=False)
    interaction_source = serializers.ChoiceField(
        choices=InteractionLog.SourceType.choices,
        default=InteractionLog.SourceType.DETAIL_PAGE,
        required=False,
    )

    def validate_reaction(self, value: str | None) -> str | None:
        if value is not None and value not in REACTION_CHOICES:
            raise CustomAPIException(ErrorMessages.INVALID_REACTION)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "is_saved" not in attrs and "reaction" not in attrs:
            raise CustomAPIException(ErrorMessages.REACTION_DATA_REQUIRED)
        return attrs


class PreferenceGameReactionResponseSerializer(serializers.Serializer[UserGameAffinity]):
    game_id = serializers.IntegerField(source="game.id")
    is_saved = serializers.BooleanField()
    reaction = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField(source="last_interacted_at")

    def get_reaction(self, obj: UserGameAffinity) -> str:
        reaction_map = {1: "like", -1: "dislike", 0: "neutral"}
        return reaction_map.get(obj.like_state, "neutral")


class SavedGameSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(source="game.id")
    name = serializers.CharField(source="game.name")
    slug = serializers.CharField(source="game.slug")
    thumbnail_img_url = serializers.CharField(source="game.thumbnail_img_url")
    rawg_rating = serializers.FloatField(source="game.rawg_rating")
    saved_at = serializers.DateTimeField(source="last_interacted_at")


class GameAffinitySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(source="game.id")
    name = serializers.CharField(source="game.name")
    is_saved = serializers.BooleanField()
    like_state = serializers.IntegerField()
    preference_score = serializers.FloatField()
    last_interacted_at = serializers.DateTimeField()