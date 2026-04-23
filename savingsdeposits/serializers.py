from rest_framework import serializers

from savingsdeposits.models import SavingsDeposit
from savings.models import SavingsAccount
from decimal import Decimal
from paymentaccounts.models import PaymentAccount


class SavingsDepositSerializer(serializers.ModelSerializer):
    savings_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=SavingsAccount.objects.all()
    )
    deposited_by = serializers.CharField(
        source="deposited_by.member_no", read_only=True
    )
    is_active = serializers.BooleanField(default=True)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all(), required=False
    )

    class Meta:
        model = SavingsDeposit
        fields = [
            "savings_account",
            "deposited_by",
            "amount",
            "phone_number",
            "description",
            "currency",
            "payment_method",
            "deposit_type",
            "transaction_status",
            "is_active",
            "receipt_number",
            "identity",
            "created_at",
            "updated_at",
            "reference",
            "checkout_request_id",
            "callback_url",
            "payment_status",
            "payment_status_description",
            "confirmation_code",
            "payment_account",
            "payment_date",
            "mpesa_receipt_number",
            "mpesa_phone_number",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
        ]


class BulkSavingsDepositSerializer(serializers.Serializer):
    deposits = SavingsDepositSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
