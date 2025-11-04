# loanapplications/serializers.py
from rest_framework import serializers
from decimal import Decimal
from datetime import date

from loanapplications.models import LoanApplication
from loanproducts.models import LoanProduct
from loanapplications.calculators import flat_rate_projection


class LoanApplicationSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)
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
        return obj.projection_snapshot

    # --- Projection Helpers ---
    def _should_recalculate_projection(self, validated_data, instance):
        fields = [
            "requested_amount",
            "term_months",
            "repayment_frequency",
            "start_date",
            "product",
        ]
        return any(
            validated_data.get(f) != getattr(instance, f)
            for f in fields
            if f in validated_data
        )

    def _generate_projection(self, validated_data, instance=None):
        if instance is None:
            product = validated_data["product"]
            principal = Decimal(validated_data["requested_amount"])
            term_months = validated_data["term_months"]
            frequency = validated_data.get("repayment_frequency", "monthly").lower()
            start_date = validated_data.get("start_date", date.today())
        else:
            product = validated_data.get("product", instance.product)
            principal = Decimal(
                validated_data.get("requested_amount", instance.requested_amount)
            )
            term_months = validated_data.get("term_months", instance.term_months)
            frequency = validated_data.get(
                "repayment_frequency", instance.repayment_frequency
            ).lower()
            start_date = validated_data.get("start_date", instance.start_date)

        return flat_rate_projection(
            principal=principal,
            annual_rate=product.interest_rate,
            term_months=term_months,
            start_date=start_date,
            repayment_frequency=frequency,
        )

    # --- Create ---
    def create(self, validated_data):
        validated_data.pop("member", None)

        projection = self._generate_projection(validated_data)
        instance = LoanApplication.objects.create(
            **validated_data,
            member=self.context["request"].user,
            projection_snapshot=projection,
            status="In Progress"
        )
        return instance

    # --- Update ---
    def update(self, instance, validated_data):
        if self._should_recalculate_projection(validated_data, instance):
            projection = self._generate_projection(validated_data, instance)
            validated_data["projection_snapshot"] = projection
            if "status" not in validated_data:
                validated_data["status"] = "In Progress"

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
