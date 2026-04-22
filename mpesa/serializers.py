from rest_framework import serializers

from mpesa.models import MpesaBody


class MpesaBodySerializer(serializers.ModelSerializer):
    body = serializers.JSONField()

    class Meta:
        model = MpesaBody
        fields = (
            "body",
            "reference",
            "created_at",
            "updated_at",
        )
