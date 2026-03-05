from rest_framework import serializers


class EmailCodeSendRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    email = serializers.EmailField(required=True)
