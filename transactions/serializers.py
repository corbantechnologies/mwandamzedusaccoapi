from rest_framework import serializers
from django.contrib.auth import get_user_model

from savings.models import SavingsAccount
from ventureaccounts.models import VentureAccount
from loanaccounts.models import LoanAccount
from savingsdeposits.models import SavingsDeposit
from venturedeposits.models import VentureDeposit
from venturepayments.models import VenturePayment

User = get_user_model()


class AccountSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    savings_accounts = serializers.SerializerMethodField()
    venture_accounts = serializers.SerializerMethodField()
    loan_accounts = serializers.SerializerMethodField()


    class Meta:
        model = User
        fields = (
            "member_no",
            "member_name",
            "savings_accounts",
            "venture_accounts",
            "loan_accounts",
        )

    def get_savings_accounts(self, obj):
        return SavingsAccount.objects.filter(member=obj).values_list(
            "account_number", "account_type__name", "balance"
        )

    def get_venture_accounts(self, obj):
        return VentureAccount.objects.filter(member=obj).values_list(
            "account_number", "venture_type__name", "balance"
        )

    def get_loan_accounts(self, obj):
        return LoanAccount.objects.filter(member=obj).values_list(
            "account_number", "product__name", "outstanding_balance"
        )

    def get_member_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class BulkUploadSerializer(serializers.Serializer):
    file = serializers.FileField()