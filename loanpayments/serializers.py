from rest_framework import serializers

from loanpayments.models import LoanPayment
from loanaccounts.models import LoanAccount
from paymentaccounts.models import PaymentAccount


class LoanPaymentSerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    paid_by = serializers.CharField(
        source="paid_by.member_no", read_only=True, required=False
    )
    payment_method = serializers.SlugRelatedField(
        slug_field="name", queryset=PaymentAccount.objects.all(), required=False
    )

    class Meta:
        model = LoanPayment
        fields = [
            "loan_account",
            "paid_by",
            "payment_method",
            "phone_number",
            "repayment_type",
            "amount",
            "transaction_status",
            "payment_code",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
            "checkout_request_id",
            "callback_url",
            "payment_status",
            "payment_status_description",
            "confirmation_code",
            "payment_account",
            "payment_date",
            "mpesa_receipt_number",
            "mpesa_phone_number",
            "reference",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        loan_account = attrs["loan_account"]
        repayment_type = attrs.get("repayment_type", "")

        # Loan Clearance and Penalty Payment amounts can exceed outstanding_balance
        # because penalties are tracked separately from the loan contract.
        # The service layer validates the exact figures for these types.
        bypass_types = {"Loan Clearance", "Penalty Payment"}

        if repayment_type not in bypass_types:
            if attrs["amount"] > loan_account.outstanding_balance:
                raise serializers.ValidationError(
                    "Amount exceeds loan outstanding balance. Current outstanding balance is "
                    f"{loan_account.outstanding_balance}"
                )
        return attrs
