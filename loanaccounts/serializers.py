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
    application_details = serializers.SerializerMethodField()

    class Meta:
        model = LoanAccount
        fields = (
            "member",
            "product",
            "application",
            "account_number",
            "principal",
            "total_loan_amount",
            "outstanding_balance",
            "start_date",
            "end_date",
            "total_interest_accrued",
            "last_interest_calulation",
            "status",
            "created_at",
            "updated_at",
            "reference",
            "application_details",
        )

    def get_application_details(self, obj):
        if obj.application:
            return {
                "reference": obj.application.reference,
                "member": obj.application.member.member_no,
                "product": obj.application.product.name,
                "amount": obj.application.requested_amount,
                "status": obj.application.status,
                "projection_snapshot": obj.application.projection_snapshot,
        }
