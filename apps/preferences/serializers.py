from typing import Any

from rest_framework import serializers


class PreferenceMeResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    genres = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_genres(self, obj: Any) -> list[dict[str, Any]]:
        pref = getattr(obj, "preference", None)
        if not pref:
            return []
        qs = pref.userpreferencegenre_set.select_related("genre").all()
        return [{"id": ug.genre.id, "name": ug.genre.name} for ug in qs]

    def get_platforms(self, obj: Any) -> list[dict[str, Any]]:
        pref = getattr(obj, "preference", None)
        if not pref:
            return []
        qs = pref.userpreferenceplatform_set.select_related("platform").all()
        return [{"id": up.platform.id, "name": up.platform.name} for up in qs]

    def get_tags(self, obj: Any) -> list[dict[str, Any]]:
        pref = getattr(obj, "preference", None)
        if not pref:
            return []
        qs = pref.userpreferencetag_set.select_related("tag").all()
        return [{"id": ut.tag.id, "name": ut.tag.name} for ut in qs]


class PreferenceGenresUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    genre_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )

    def validate_genre_ids(self, value: list[int]) -> list[int]:
        from apps.games.models import Genre

        existing = set(Genre.objects.filter(id__in=value).values_list("id", flat=True))
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                detail=f"존재하지 않는 장르 id: {sorted(missing)}",
                code="invalid_genre_id",
            )
        return value


class PreferencePlatformsUpdateSerializer(serializers.Serializer):  # type: ignore[type-arg]
    platform_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )

    def validate_platform_ids(self, value: list[int]) -> list[int]:
        from apps.games.models import Platform

        existing = set(Platform.objects.filter(id__in=value).values_list("id", flat=True))
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(
                detail=f"존재하지 않는 플랫폼 id: {sorted(missing)}",
                code="invalid_platform_id",
            )
        return value
