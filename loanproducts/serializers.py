from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from loanproducts.models import LoanProduct


class LoanProductSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        validators=[UniqueValidator(queryset=LoanProduct.objects.all())]
    )

    class Meta:
        model = LoanProduct
        fields = (
            "name",
            "interest_rate",
            "interest_period",
            "calculation_schedule",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
        )
