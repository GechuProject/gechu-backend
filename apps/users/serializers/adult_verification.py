from rest_framework import serializers


class AdultVerificationCallbackRequestSerializer(serializers.Serializer[dict[str, object]]):
    code = serializers.CharField()
    state = serializers.CharField()


class AdultVerificationCallbackResponseSerializer(serializers.Serializer[dict[str, object]]):
    is_adult_verified = serializers.BooleanField()
    adult_verified_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()


class AdultVerificationStatusResponseSerializer(serializers.Serializer[dict[str, object]]):
    is_adult_verified = serializers.BooleanField()
    adult_verified_at = serializers.DateTimeField(allow_null=True)
    adult_verified_until = serializers.DateTimeField(allow_null=True)
