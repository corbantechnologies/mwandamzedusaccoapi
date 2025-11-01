from rest_framework import serializers

from loanapplications.models import LoanApplication
from loanproducts.models import LoanProduct


class LoanApplicationSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_number")
    product = serializers.SlugRelatedField(
        slug_field="name",
        queryset=LoanProduct.objects.filter(is_active=True),
    )
    requested_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=1
    )

    class Meta:
        model = LoanApplication
        fields = "__all__"
