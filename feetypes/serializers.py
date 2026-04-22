from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from feetypes.models import FeeType
from glaccounts.models import GLAccount


class FeeTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=FeeType.objects.all())]
    )
    gl_account = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )

    class Meta:
        model = FeeType
        fields = (
            "id",
            "reference",
            "name",
            "amount",
            "is_everyone",
            "can_exceed_limit",
            "gl_account",
            "is_active",
            "created_at",
            "updated_at",
        )


class BulkFeeTypeSerializer(serializers.Serializer):
    fee_types = FeeTypeSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
