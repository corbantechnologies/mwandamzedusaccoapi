from rest_framework import serializers
from loanapplications.models import LoanApplication
from loanproducts.models import LoanProduct
from loanapplications.calculators import flat_rate_projection
from decimal import Decimal
from datetime import date


class LoanApplicationSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_number", read_only=True)
    product = serializers.SlugRelatedField(
        slug_field="name",
        queryset=LoanProduct.objects.filter(is_active=True),
    )
    requested_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=1
    )
    start_date = serializers.DateField(default=date.today)
    projection = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = (
            "id",
            "member",
            "product",
            "requested_amount",
            "term_months",
            "repayment_frequency",
            "start_date",
            "status",
            "projection",
            "created_at",
            "reference",
        )
        read_only_fields = ("status", "projection", "created_at", "reference")

    def get_projection(self, obj):
        if obj.projection_snapshot:
            return obj.projection_snapshot
        return None

    def create(self, validated_data):
        product = validated_data["product"]
        principal = Decimal(validated_data["requested_amount"])
        term_months = validated_data["term_months"]
        frequency = validated_data["repayment_frequency"].lower()
        start_date = validated_data["start_date"]

        # Generate projection
        projection = flat_rate_projection(
            principal=principal,
            annual_rate=product.interest_rate,
            term_months=term_months,
            start_date=start_date,
            repayment_frequency=frequency,
        )

        # Save snapshot
        instance = LoanApplication.objects.create(
            **validated_data,
            projection_snapshot=projection,
            status="In Progress"  # Auto-move to In Progress
        )
        return instance
