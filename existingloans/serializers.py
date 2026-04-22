from rest_framework import serializers
from django.contrib.auth import get_user_model

from existingloans.models import ExistingLoan
from paymentaccounts.models import PaymentAccount
from glaccounts.models import GLAccount
from existingloanspayments.serializers import ExistingLoanPaymentSerializer

User = get_user_model()


class ExistingLoanSerializer(serializers.ModelSerializer):
    member = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field="member_no"
    )
    payment_method = serializers.SlugRelatedField(
        queryset=PaymentAccount.objects.all(), slug_field="name"
    )
    gl_principal_asset = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    gl_penalty_revenue = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    gl_interest_revenue = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    existing_loan_payments = ExistingLoanPaymentSerializer(many=True, read_only=True)
    outstanding_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = ExistingLoan
        fields = (
            "id",
            "member",
            "account_number",
            "payment_method",
            "principal",
            "outstanding_balance",
            "total_amount_paid",
            "total_interest_paid",
            "total_penalties_paid",
            "status",
            "reference",
            "created_at",
            "updated_at",
            "posted_to_gl",
            "balance_updated",
            "accounting_error",
            "gl_principal_asset",
            "gl_penalty_revenue",
            "gl_interest_revenue",
            "existing_loan_payments",
        )


class BulkExistingLoanSerializer(serializers.Serializer):
    loans = ExistingLoanSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
