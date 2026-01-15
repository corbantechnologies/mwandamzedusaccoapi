from rest_framework import serializers

from loanpayments.models import LoanPayment
from loanaccounts.models import LoanAccount


class LoanPaymentSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    paid_by = serializers.CharField(
        source="paid_by.member_no", read_only=True, required=False
    )

    class Meta:
        model = LoanPayment
        fields = [
            "loan_account",
            "paid_by",
            "payment_method",
            "repayment_type",
            "amount",
            "transaction_status",
            "payment_date",
            "payment_code",
            "reference",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        loan_account = attrs["loan_account"]
        if attrs["amount"] > loan_account.outstanding_balance:
            raise serializers.ValidationError(
                "Amount exceeds loan outstanding balance. Current outstanding balance is "
                f"{loan_account.outstanding_balance}"
            )
        return attrs
