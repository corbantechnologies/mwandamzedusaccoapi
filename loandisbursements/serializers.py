from rest_framework import serializers
from loandisbursements.models import LoanDisbursement
from django.contrib.auth import get_user_model

from loanaccounts.models import LoanAccount
from paymentaccounts.models import PaymentAccount

User = get_user_model()


class LoanDisbursementSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    disbursed_by = serializers.CharField(
        source="disbursed_by.member_no", read_only=True, required=False
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all()
    )

    class Meta:
        model = LoanDisbursement
        fields = [
            "loan_account",
            "disbursed_by",
            "amount",
            "currency",
            "transaction_status",
            "disbursement_type",
            "transaction_code",
            "created_at",
            "updated_at",
            "reference",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
            "payment_method",
        ]


class BulkLoanDisbursementSerializer(serializers.Serializer):
    disbursements = LoanDisbursementSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
