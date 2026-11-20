from rest_framework import serializers

from .models import OperationLog


class UssdRequestSerializer(serializers.Serializer):
    msisdn = serializers.CharField(max_length=15)
    session_id = serializers.CharField(max_length=128)
    input = serializers.CharField(allow_blank=True)


class UssdResponseSerializer(serializers.Serializer):
    text = serializers.CharField()
    end = serializers.BooleanField()


class OperationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationLog
        fields = ["id", "msisdn", "op_type", "details", "status", "created_at"]
