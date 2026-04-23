from rest_framework import serializers

from loanpenalties.models import LoanPenalty
from loanaccounts.models import LoanAccount


class LoanPenaltySerializer(serializers.ModelSerializer):
    loan_account = serializers.SlugRelatedField(
        slug_field="account_number", queryset=LoanAccount.objects.all()
    )
    charged_by = serializers.CharField(source="charged_by.member_no", read_only=True)
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        return str(obj.balance)

    class Meta:
        model = LoanPenalty
        fields = [
            "id",
            "penalty_code",
            "loan_account",
            "installment_code",
            "amount",
            "amount_paid",
            "balance",
            "status",
            "charged_by",
            "created_at",
            "updated_at",
            "reference",
        ]
        read_only_fields = [
            "amount",
            "charged_by",
            "installment_code",
        ]
