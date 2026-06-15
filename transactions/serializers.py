from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.models import SavingsAccount
from loanaccounts.models import LoanAccount
from feeaccounts.models import FeeAccount
from savingsdeposits.models import SavingsDeposit

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    savings_accounts = serializers.SerializerMethodField()
    fee_accounts = serializers.SerializerMethodField()
    loan_accounts = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "member_no",
            "member_name",
            "savings_accounts",
            "fee_accounts",
            "loan_accounts",
        )

    def get_savings_accounts(self, obj):
        return SavingsAccount.objects.filter(member=obj).values_list(
            "account_number", "account_type__name", "balance"
        )

    def get_fee_accounts(self, obj):
        return FeeAccount.objects.filter(member=obj).values_list(
            "account_number", "fee_type__name", "outstanding_balance"
        )

    def get_loan_accounts(self, obj):
        return LoanAccount.objects.filter(member=obj).values_list(
            "account_number", "product__name", "outstanding_balance"
        )

    def get_member_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class BulkUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    payment_method = serializers.CharField(required=False, allow_blank=True, allow_null=True)
