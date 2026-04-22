from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from loanproducts.models import LoanProduct
from glaccounts.models import GLAccount


class LoanProductSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=LoanProduct.objects.all())]
    )
    is_active = serializers.BooleanField(default=True)
    gl_principal_asset = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    gl_penalty_revenue = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    gl_interest_revenue = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )
    gl_processing_fee_revenue = serializers.SlugRelatedField(
        slug_field="name", queryset=GLAccount.objects.all()
    )

    class Meta:
        model = LoanProduct
        fields = (
            "name",
            "interest_method",
            "interest_rate",
            "processing_fee",
            "interest_period",
            "calculation_schedule",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
            "gl_principal_asset",
            "gl_penalty_revenue",
            "gl_interest_revenue",
            "gl_processing_fee_revenue",
        )


class BulkLoanProductSerializer(serializers.Serializer):
    loan_products = LoanProductSerializer(many=True)


class BulkUploadFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="CSV file for bulk upload", required=True)
