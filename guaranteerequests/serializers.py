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
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )
    loan_application_details = serializers.SerializerMethodField()
    guarantor_name = serializers.SerializerMethodField()
    remaining_to_cover = serializers.SerializerMethodField()

    def get_guarantor_name(self, obj):
        return obj.guarantor.member.get_full_name()

    def get_loan_application_details(self, obj):
        return {
            "reference": obj.loan_application.reference,
            "member": obj.loan_application.member.member_no,
            "product": obj.loan_application.product.name,
            "amount": obj.loan_application.requested_amount,
            "status": obj.loan_application.status,
            "remaining_to_cover": compute_loan_coverage(obj.loan_application)[
                "remaining_to_cover"
            ],
            "projection_snapshot": obj.loan_application.projection_snapshot,
        }

    def get_remaining_to_cover(self, obj):
        return compute_loan_coverage(obj.loan_application)["remaining_to_cover"]

    class Meta:
        model = GuaranteeRequest
        fields = (
            "member",
            "guarantor_name",
            "loan_application",
            "guarantor",
            "guaranteed_amount",
            "status",
            "notes",
            "created_at",
            "updated_at",
            "reference",
            "remaining_to_cover",
            "loan_application_details",
        )

    def validate(self, data):
        request = self.context["request"]
        member = request.user
        loan_app = data["loan_application"]
        guarantor = data["guarantor"]
        amount = data.get("guaranteed_amount")
        remaining_to_cover = compute_loan_coverage(loan_app)["remaining_to_cover"]

        if loan_app.member != member:
            raise serializers.ValidationError(
                {
                    "loan_application": "You can only request guarantees for your own applications."
                }
            )

        # Application must be in a state that allows guarantees
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {
                    "loan_application": f"Cannot add guarantor to application in '{loan_app.status}' state."
                }
            )

        # Validation if amount is provided (Self-guarantee or update)
        if amount:
            # you cannot apply more than what is required
            if amount > remaining_to_cover:
                raise serializers.ValidationError(
                    {
                        "guaranteed_amount": f"You cannot guarantee more than what is required. Remaining to cover: {remaining_to_cover}"
                    }
                )

            # Use real available capacity
            available = guarantor.available_capacity()
            current_committed = guarantor.committed_guarantee_amount

            if self.instance:
                # If updating, subtract the old amount
                old_amount = self.instance.guaranteed_amount or Decimal("0")
                current_committed -= old_amount

            if current_committed + amount > guarantor.max_guarantee_amount:
                raise serializers.ValidationError(
                    {
                        "guaranteed_amount": (
                            f"Guarantor only has {available} available. "
                            f"Currently committed: {current_committed}."
                        )
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

        return data

    def create(self, validated_data):
        validated_data["member"] = self.context["request"].user
        instance = super().create(validated_data)

        # AUTO-ACCEPT SELF-GUARANTEE ONLY if amount is provided
        if instance.guarantor.member == instance.member and instance.guaranteed_amount:
            instance.status = "Accepted"
            instance.save(update_fields=["status"])

            loan = instance.loan_application
            loan.self_guaranteed_amount = instance.guaranteed_amount
            loan.save(update_fields=["self_guaranteed_amount"])

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
