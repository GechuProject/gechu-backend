from rest_framework import serializers


class EmailCodeSendRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)