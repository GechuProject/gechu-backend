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
        return [{"id": g.id, "name": g.name} for g in pref.genres.all()]

    def get_platforms(self, obj: Any) -> list[dict[str, Any]]:
        pref = getattr(obj, "preference", None)
        if not pref:
            return []
        return [{"id": p.id, "name": p.name} for p in pref.platforms.all()]

    def get_tags(self, obj: Any) -> list[dict[str, Any]]:
        pref = getattr(obj, "preference", None)
        if not pref:
            return []
        return [{"id": t.id, "name": t.name} for t in pref.tags.all()]


