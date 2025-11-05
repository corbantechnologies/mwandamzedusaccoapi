from rest_framework import serializers
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import models

from loanapplications.models import LoanApplication
from loanproducts.models import LoanProduct
from loanapplications.calculators import flat_rate_projection
from mwandamzeduapi.settings import (
    FIRST_LOAN_MAX_SAVINGS_PERCENT,
    FIRST_LOAN_MIN_MEMBER_MONTHS,
)
from loanaccounts.models import LoanAccount
from savings.models import SavingsAccount


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
    can_submit = serializers.SerializerMethodField(read_only=True)
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
            "can_submit",
            "projection",
            "created_at",
            "reference",
        )
        read_only_fields = ("status", "projection", "created_at", "reference")

    def get_projection(self, obj):
        return obj.projection_snapshot

    def get_can_submit(self, obj):
        return self._can_submit_without_guarantors(obj)

    # --- Helpers ---
    def _is_first_loan(self, member):
        return not LoanAccount.objects.filter(member=member).exists()

    def _total_savings(self, member):
        total = SavingsAccount.objects.filter(member=member).aggregate(
            total=models.Sum("balance")
        )["total"]
        return total or Decimal("0")

    def _can_submit_without_guarantors(self, instance):
        member = instance.member
        amount = instance.requested_amount
        savings = self._total_savings(member)

        # Rule 3: Savings ≥ Loan → can submit
        if savings >= amount:
            return True

        # Rule 1 & 2: First-time borrower
        if self._is_first_loan(member):
            months = int(FIRST_LOAN_MIN_MEMBER_MONTHS)
            required_date = timezone.now() - relativedelta(months=months)
            if member.created_at <= required_date:
                max_allowed = savings * Decimal(FIRST_LOAN_MAX_SAVINGS_PERCENT) / 100
                return amount <= max_allowed

        return False

    # --- Validation ---
    def validate(self, data):
        request = self.context["request"]
        member = request.user

        # Build temp instance
        temp_instance = LoanApplication(
            member=member,
            requested_amount=data["requested_amount"],
            **{
                k: data.get(k)
                for k in ["product", "term_months", "repayment_frequency", "start_date"]
            },
        )

        # Rule 1 & 2: First-time borrower
        if self._is_first_loan(member):
            # 2. Member age
            months = int(FIRST_LOAN_MIN_MEMBER_MONTHS)
            required_date = timezone.now() - relativedelta(months=months)
            if member.created_at > required_date:
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            f"Must be a member for {months}+ months to apply for first loan."
                        ]
                    }
                )

            # 1. Max 80% of savings
            savings = self._total_savings(member)
            max_allowed = savings * Decimal(FIRST_LOAN_MAX_SAVINGS_PERCENT) / 100
            if data["requested_amount"] > max_allowed:
                raise serializers.ValidationError(
                    {
                        "requested_amount": f"First-time loan limited to {FIRST_LOAN_MAX_SAVINGS_PERCENT}% of savings (max: {max_allowed})."
                    }
                )

        # Set status based on readiness
        if self._can_submit_without_guarantors(temp_instance):
            data["status"] = "Ready for Submission"
        else:
            data["status"] = "In Progress"

        return data

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
        projection = self._generate_projection(validated_data)
        instance = LoanApplication.objects.create(
            member=self.context["request"].user,
            projection_snapshot=projection,
            **validated_data,
        )
        return instance

    # --- Update ---
    def update(self, instance, validated_data):
        if self._should_recalculate_projection(validated_data, instance):
            projection = self._generate_projection(validated_data, instance)
            validated_data["projection_snapshot"] = projection

        # Re-evaluate readiness
        temp_instance = LoanApplication(
            member=instance.member,
            requested_amount=validated_data.get(
                "requested_amount", instance.requested_amount
            ),
            **{
                k: validated_data.get(k, getattr(instance, k))
                for k in ["product", "term_months", "repayment_frequency", "start_date"]
            },
        )

        if self._can_submit_without_guarantors(temp_instance):
            validated_data["status"] = "Ready for Submission"
        else:
            validated_data["status"] = "In Progress"

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
