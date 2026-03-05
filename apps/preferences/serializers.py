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


