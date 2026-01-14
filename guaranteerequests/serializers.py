from rest_framework import serializers
from decimal import Decimal

from guaranteerequests.models import GuaranteeRequest
from loanapplications.models import LoanApplication
from guarantors.models import GuarantorProfile
from loanapplications.utils import compute_loan_coverage


class GuaranteeRequestSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.member_no", read_only=True)

    guarantor = serializers.SlugRelatedField(
        slug_field="member__member_no",
        queryset=GuarantorProfile.objects.filter(is_eligible=True),
    )
    loan_application = serializers.SlugRelatedField(
        slug_field="reference", queryset=LoanApplication.objects.all()
    )
    guaranteed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = GuaranteeRequest
        fields = (
            "member",
            "loan_application",
            "guarantor",
            "guaranteed_amount",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "reference",
        )

    def validate(self, data):
        request = self.context["request"]
        member = request.user
        loan_app = data["loan_application"]
        guarantor = data["guarantor"]
        amount = data["guaranteed_amount"]

        if loan_app.member != member:
            raise serializers.ValidationError(
                {
                    "loan_application": "You can only request guarantees for your own applications."
                }
            )

        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {
                    "loan_application": f"Cannot add guarantor to application in '{loan_app.status}' state."
                }
            )

        # Use real available capacity
        available = guarantor.available_capacity()
        current_committed = guarantor.committed_guarantee_amount

        if self.instance:
            current_committed -= self.instance.guaranteed_amount

        if current_committed + amount > guarantor.max_guarantee_amount:
            raise serializers.ValidationError(
                {
                    "guaranteed_amount": (
                        f"Guarantor only has {available} available. "
                        f"Currently committed: {current_committed}."
                    )
                }
            )

        if (
            GuaranteeRequest.objects.filter(
                loan_application=loan_app, guarantor=guarantor
            )
            .exclude(reference=self.instance.reference if self.instance else None)
            .exists()
        ):
            raise serializers.ValidationError(
                {
                    "guarantor": "This member is already a guarantor for this application."
                }
            )

        # SELF-GUARANTEE: use application-level available
        if guarantor.member == member:
            coverage = compute_loan_coverage(loan_app)
            if amount > coverage["available_self_guarantee"]:
                raise serializers.ValidationError(
                    {
                        "guaranteed_amount": f"Self-guarantee limited to {coverage['available_self_guarantee']}"
                    }
                )

        return data

    def create(self, validated_data):
        validated_data["member"] = self.context["request"].user
        instance = super().create(validated_data)

        # AUTO-ACCEPT SELF-GUARANTEE ONLY
        if instance.guarantor.member == instance.member:
            instance.status = "Accepted"
            instance.save(update_fields=["status"])

            loan = instance.loan_application
            loan.self_guaranteed_amount = instance.guaranteed_amount
            loan.save(update_fields=["self_guaranteed_amount"])

            # Reserve for self (already handled in submit view)
            # → No double-reservation here

            if compute_loan_coverage(loan)["is_fully_covered"]:
                loan.status = "Ready for Submission"
                loan.save(update_fields=["status"])

        return instance


class GuaranteeApprovalDeclineSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["Accepted", "Declined"], required=True)
    guaranteed_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01"), required=False
    )

    class Meta:
        model = GuaranteeRequest
        fields = ("status", "guaranteed_amount")
