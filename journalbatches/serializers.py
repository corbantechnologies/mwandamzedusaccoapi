from rest_framework import serializers

from journalbatches.models import JournalBatch
from journalentries.serializers import JournalEntrySerializer
from journalentries.models import JournalEntry
from glaccounts.models import GLAccount


class JournalBatchSerializer(serializers.ModelSerializer):
    entries = JournalEntrySerializer(many=True, read_only=True)

    class Meta:
        model = JournalBatch
        fields = (
            "id",
            "code",
            "description",
            "posted",
            "created_at",
            "updated_at",
            "reference",
            "entries",
        )


class BulkJournalEntrySerializer(serializers.ModelSerializer):
    account = serializers.SlugRelatedField(
        queryset=GLAccount.objects.all(), slug_field="name"
    )

    class Meta:
        model = JournalEntry
        fields = ["account", "debit", "credit"]


class BulkJournalBatchSerializer(serializers.ModelSerializer):
    entries = BulkJournalEntrySerializer(many=True)

    class Meta:
        model = JournalBatch
        fields = ["description", "entries", "reference"]


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
