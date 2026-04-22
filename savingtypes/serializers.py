from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from savingtypes.models import SavingType
from glaccounts.models import GLAccount


class SavingTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=SavingType.objects.all())]
    )
    can_guarantee = serializers.BooleanField(default=True)
    gl_account = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )

    class Meta:
        model = SavingType
        fields = (
            "id",
            "name",
            "interest_rate",
            "gl_account",
            "can_guarantee",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )


class BulkSavingTypeSerializer(serializers.Serializer):
    saving_types = SavingTypeSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
