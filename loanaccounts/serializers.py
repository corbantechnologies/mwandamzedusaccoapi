from rest_framework import serializers

from loanaccounts.models import LoanAccount
from loanproducts.models import LoanProduct


class LoanAccountSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_number")
    product = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanProduct.objects.all()
    )

    class Meta:
        model = LoanAccount
        fields = (
            "member",
            "product",
            "account_number",
            "principal",
            "outstanding_balance",
            "start_date",
            "end_date",
            "last_interest_calulation",
            "status",
            "created_at",
            "updated_at",
            "reference",
        )