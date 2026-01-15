from rest_framework import serializers
from loandisbursements.models import LoanDisbursement
from django.contrib.auth import get_user_model

from loanaccounts.models import LoanAccount

User = get_user_model()


class LoanDisbursementSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    disbursed_by = serializers.CharField(
        source="disbursed_by.member_no", read_only=True, required=False
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
        ]
