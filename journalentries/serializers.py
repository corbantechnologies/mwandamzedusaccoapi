from rest_framework import serializers

from journalentries.models import JournalEntry
from glaccounts.models import GLAccount
from journalbatches.models import JournalBatch


class JournalEntrySerializer(serializers.ModelSerializer):
    # these are not required as the entries will mostly be created by the system unless an updating is being done or a manual entry is being made
    created_by = serializers.CharField(
        read_only=True, required=False, source="created_by.member_no"
    )
    updated_by = serializers.CharField(
        read_only=True, required=False, source="updated_by.member_no"
    )
    account = serializers.SlugRelatedField(
        queryset=GLAccount.objects.all(), slug_field="name"
    )
    batch = serializers.SlugRelatedField(
        queryset=JournalBatch.objects.all(), slug_field="code"
    )

    account_details = serializers.SerializerMethodField()
    batch_details = serializers.SerializerMethodField()

    def get_account_details(self, obj):
        return {
            "id": obj.account.id,
            "code": obj.account.code,
            "name": obj.account.name,
            "category": obj.account.category,
            "balance": obj.account.balance,
            "created_at": obj.account.created_at,
            "updated_at": obj.account.updated_at,
            "reference": obj.account.reference,
        }

    def get_batch_details(self, obj):
        return {
            "id": obj.batch.id,
            "code": obj.batch.code,
            "description": obj.batch.description,
            "created_at": obj.batch.created_at,
            "updated_at": obj.batch.updated_at,
            "reference": obj.batch.reference,
        }

    class Meta:
        model = JournalEntry
        fields = (
            "id",
            "reference",
            "code",
            "batch",
            "account",
            "debit",
            "credit",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "account_details",
            "batch_details",
        )
