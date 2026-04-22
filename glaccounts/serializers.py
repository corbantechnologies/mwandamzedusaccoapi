from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from glaccounts.models import GLAccount
from journalentries.serializers import JournalEntrySerializer


class GLAccountSerializer(serializers.ModelSerializer):
    """
    GL Account Serializer
    """

    name = serializers.CharField(
        max_length=2505,
        validators=[
            UniqueValidator(
                queryset=GLAccount.objects.all(),
                message="GL Account name already exists.",
            )
        ],
    )
    code = serializers.CharField(
        max_length=20,
        validators=[
            UniqueValidator(
                queryset=GLAccount.objects.all(),
                message="GL Account code already exists.",
            )
        ],
    )
    entries = JournalEntrySerializer(many=True, read_only=True)

    class Meta:
        model = GLAccount
        fields = (
            "id",
            "name",
            "code",
            "category",
            "balance",
            "is_active",
            "is_current_account",
            "created_at",
            "updated_at",
            "reference",
            "entries",
        )


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)


class BulkGLAccountSerializer(serializers.Serializer):
    accounts = GLAccountSerializer(many=True)
