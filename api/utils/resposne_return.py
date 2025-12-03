from rest_framework import serializers


class APIResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.DictField(child=serializers.CharField(), default={})
