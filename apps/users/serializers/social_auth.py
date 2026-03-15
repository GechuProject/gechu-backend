from rest_framework import serializers


class SocialCallbackRequestSerializer(serializers.Serializer[dict[str, object]]):
    code = serializers.CharField()
    state = serializers.CharField()


class SocialLoginResponseSerializer(serializers.Serializer[dict[str, object]]):
    access_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()
    is_new_user = serializers.BooleanField()
