from rest_framework import serializers
from django.contrib.auth import get_user_model

from loanaccounts.models import LoanAccount
from loanproducts.models import LoanProduct
from loanapplications.models import LoanApplication

User = get_user_model()

class LoanAccountSerializer(serializers.ModelSerializer):
    member = serializers.SlugRelatedField(
        slug_field="member_no", queryset=User.objects.all()
    )
    product = serializers.SlugRelatedField(
        slug_field="name", queryset=LoanProduct.objects.all()
    )
    application = serializers.SlugRelatedField(
        slug_field="reference", queryset=LoanApplication.objects.all(), required=False
    )

    class Meta:
        model = LoanAccount
        fields = (
            "member",
            "product",
            "application",
            "account_number",
            "principal",
            "outstanding_balance",
            "start_date",
            "end_date",
            "total_interest_accrued",
            "last_interest_calulation",
            "status",
            "created_at",
            "updated_at",
            "reference",
        )
