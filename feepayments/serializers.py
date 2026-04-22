from rest_framework import serializers
from django.contrib.auth import get_user_model

from feepayments.models import FeePayment
from feeaccounts.models import FeeAccount
from paymentaccounts.models import PaymentAccount

User = get_user_model()


class FeePaymentSerializer(serializers.ModelSerializer):
    paid_by = serializers.CharField(source="paid_by.member_no", read_only=True)
    fee_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=FeeAccount.objects.all()
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all()
    )

    class Meta:
        model = FeePayment
        fields = (
            "id",
            "reference",
            "amount",
            "paid_by",
            "fee_account",
            "payment_method",
            "transaction_status",
            "phone_number",
            "currency",
            "code",
            # Mpesa fields:
            "checkout_request_id",
            "callback_url",
            "payment_status",
            "payment_status_description",
            "confirmation_code",
            "payment_account",
            "payment_date",
            "mpesa_receipt_number",
            "mpesa_phone_number",
            "created_at",
            "updated_at",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
        )


class BulkFeePaymentSerializer(serializers.Serializer):
    fee_payments = FeePaymentSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
