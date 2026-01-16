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
from loanapplications.utils import compute_loan_coverage


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

    # Computed fields
    total_savings = serializers.SerializerMethodField()
    available_self_guarantee = serializers.SerializerMethodField()
    total_guaranteed_by_others = serializers.SerializerMethodField()
    effective_coverage = serializers.SerializerMethodField()
    remaining_to_cover = serializers.SerializerMethodField()
    is_fully_covered = serializers.SerializerMethodField()

    # loan account: can be blank if the application is not approved
    loan_account = serializers.CharField(
        source="loan_account.account_number",
        read_only=True,
    )

    class Meta:
        model = LoanApplication
        fields = (
            "member",
            "product",
            "requested_amount",
            "term_months",
            "repayment_frequency",
            "repayment_amount",
            "total_interest",
            "start_date",
            "status",
            "can_submit",
            "self_guaranteed_amount",
            "total_savings",
            "available_self_guarantee",
            "total_guaranteed_by_others",
            "effective_coverage",
            "remaining_to_cover",
            "is_fully_covered",
            "amendment_note",
            "created_at",
            "updated_at",
            "reference",
            "loan_account",
            "projection",
        )

    # --- Computed Methods ---
    def get_total_savings(self, obj):
        return float(compute_loan_coverage(obj)["total_savings"])

    def get_committed_self_guarantee(self, obj):
        return float(compute_loan_coverage(obj)["committed_self_guarantee"])

    def get_available_self_guarantee(self, obj):
        return float(compute_loan_coverage(obj)["available_self_guarantee"])

    def get_total_guaranteed_by_others(self, obj):
        return float(compute_loan_coverage(obj)["total_guaranteed_by_others"])

    def get_effective_coverage(self, obj):
        return float(compute_loan_coverage(obj)["effective_coverage"])

    def get_remaining_to_cover(self, obj):
        return float(compute_loan_coverage(obj)["remaining_to_cover"])

    def get_is_fully_covered(self, obj):
        return compute_loan_coverage(obj)["is_fully_covered"]

    def get_projection(self, obj):
        return obj.projection_snapshot

    def get_can_submit(self, obj):
        return compute_loan_coverage(obj)["is_fully_covered"]

    # --- Helpers ---
    def _is_first_loan(self, member):
        return not LoanAccount.objects.filter(member=member).exists()

    def _total_savings(self, member):
        total = SavingsAccount.objects.filter(
            member=member, account_type__can_guarantee=True
        ).aggregate(total=models.Sum("balance"))["total"]
        return total or Decimal("0")

    # --- Validation ---
    def validate(self, data):
        request = self.context["request"]
        member = request.user

        if not self.instance and "requested_amount" not in data:
            raise serializers.ValidationError(
                {"requested_amount": "This field is required."}
            )

        requested_amount = data.get("requested_amount")
        if requested_amount is None and self.instance:
            requested_amount = self.instance.requested_amount
        if requested_amount is None:
            raise serializers.ValidationError(
                {"requested_amount": "This field is required."}
            )

        # Build temp instance
        temp_instance = LoanApplication(
            member=member,
            requested_amount=requested_amount,
            product=data.get("product", getattr(self.instance, "product", None)),
            term_months=data.get(
                "term_months", getattr(self.instance, "term_months", None)
            ),
            repayment_frequency=data.get(
                "repayment_frequency",
                getattr(self.instance, "repayment_frequency", "monthly"),
            ),
            start_date=data.get(
                "start_date", getattr(self.instance, "start_date", date.today())
            ),
        )

        # First-time borrower rules
        if self._is_first_loan(member) and (
            "requested_amount" in data or not self.instance
        ):
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

            savings = self._total_savings(member)
            max_allowed = savings * Decimal(FIRST_LOAN_MAX_SAVINGS_PERCENT) / 100
            if requested_amount > max_allowed:
                raise serializers.ValidationError(
                    {
                        "requested_amount": f"First-time loan limited to {FIRST_LOAN_MAX_SAVINGS_PERCENT}% of savings (max: {max_allowed})."
                    }
                )

        # SET STATUS
        data["status"] = "Pending"  # Always start as pending

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
        validated_data.pop("member", None)
        projection = self._generate_projection(validated_data)
        instance = LoanApplication.objects.create(
            member=self.context["request"].user,
            projection_snapshot=projection,
            repayment_amount=projection["total_repayment"],
            total_interest=projection["total_interest"],
            **validated_data,
        )
        return instance

    # --- Update ---
    def update(self, instance, validated_data):
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if instance.status in FINAL_STATES:
            raise serializers.ValidationError(
                {"detail": f"Cannot update application in '{instance.status}' state."}
            )

        if self._should_recalculate_projection(validated_data, instance):
            projection = self._generate_projection(validated_data, instance)
            validated_data["projection_snapshot"] = projection
            validated_data["repayment_amount"] = projection["total_repayment"]
            validated_data["total_interest"] = projection["total_interest"]

        # Re-evaluate status using coverage
        requested_amount = validated_data.get(
            "requested_amount", instance.requested_amount
        )
        temp_instance = LoanApplication(
            member=instance.member,
            requested_amount=requested_amount,
            product=validated_data.get("product", instance.product),
            term_months=validated_data.get("term_months", instance.term_months),
            repayment_frequency=validated_data.get(
                "repayment_frequency", instance.repayment_frequency
            ),
            start_date=validated_data.get("start_date", instance.start_date),
        )

        if "status" in validated_data:
            instance.status = validated_data["status"]

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LoanStatusUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(
        choices=LoanApplication.STATUS_CHOICES, required=True
    )

    class Meta:
        model = LoanApplication
        fields = ("status",)
