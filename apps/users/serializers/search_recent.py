from rest_framework import serializers


class RecentSearchListResponseSerializer(serializers.Serializer[dict[str, object]]):
    results = serializers.ListField(child=serializers.CharField())


class RecentSearchDeleteResponseSerializer(serializers.Serializer[dict[str, object]]):
    message = serializers.CharField()
