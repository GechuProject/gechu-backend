from rest_framework import serializers


class ErrorResponseSerializer(serializers.Serializer):  # type: ignore[type-arg]
    status_code = serializers.IntegerField()
    code = serializers.CharField()
    message = serializers.CharField()
