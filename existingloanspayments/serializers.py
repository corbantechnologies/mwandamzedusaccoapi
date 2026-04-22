from rest_framework import serializers

from existingloanspayments.models import ExistingLoanPayment
from existingloans.models import ExistingLoan
from paymentaccounts.models import PaymentAccount
from accounts.models import User


class ExistingLoanPaymentSerializer(serializers.ModelSerializer):
    existing_loan = serializers.SlugRelatedField(
        slug_field="account_number", queryset=ExistingLoan.objects.all()
    )
    paid_by = serializers.CharField(
        source="paid_by.member_no", read_only=True, required=False
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all()
    )

    class Meta:
        model = ExistingLoanPayment
        fields = [
            "id",
            "reference",
            "existing_loan",
            "paid_by",
            "payment_method",
            "repayment_type",
            "amount",
            "transaction_status",
            "payment_date",
            "payment_code",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
            "created_at",
            "updated_at",
            "checkout_request_id",
            "callback_url",
            "payment_status",
            "payment_status_description",
            "confirmation_code",
            "mpesa_receipt_number",
            "mpesa_phone_number",
        ]


class BulkExistingLoanPaymentSerializer(serializers.Serializer):
    payments = ExistingLoanPaymentSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
