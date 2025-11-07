from rest_framework import serializers
from decimal import Decimal

from guaranteerequests.models import GuaranteeRequest
from loanapplications.models import LoanApplication
from guarantors.models import GuarantorProfile


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

        # 1. Own application
        if loan_app.member != member:
            raise serializers.ValidationError(
                {
                    "loan_application": "You can only request guarantees for your own applications."
                }
            )

        # 2. Not final state
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {
                    "loan_application": f"Cannot add guarantor to application in '{loan_app.status}' state."
                }
            )

        # 3. Use method & stored field
        current_committed = guarantor.committed_amount()
        max_allowed = guarantor.max_guarantee_amount

        if self.instance:
            current_committed -= self.instance.guaranteed_amount

        if current_committed + amount > max_allowed:
            available = max_allowed - current_committed
            print(available)
            raise serializers.ValidationError(
                {
                    "guaranteed_amount": (
                        f"Guarantor can only guarantee up to {max_allowed}. "
                        f"Currently committed: {current_committed}. "
                        f"Available: {available}."
                    )
                }
            )

        # 4. No duplicate
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

        # SELF-GUARANTEE
        if guarantor.member == member:
            available = loan_app.available_self_guarantee
            if data["guaranteed_amount"] > available:
                raise serializers.ValidationError(
                    {"guaranteed_amount": f"Self-guarantee available: {available}"}
                )

        return data

    def create(self, validated_data):
        validated_data["member"] = self.context["request"].user
        instance = super().create(validated_data)

        # AUTO-ACCEPT SELF-GUARANTEE
        if instance.guarantor.member == instance.member:
            instance.status = "Approved"
            instance.save(update_fields=["status"])

            # update loan
            loan = instance.loan_application
            loan.self_guaranteed_amount = instance.guaranteed_amount
            loan.save(update_fields=["self_guaranteed_amount"])

            #  update guarantor profile
            # guarantor = instance.guarantor
            # guarantor.committed_amount += instance.guaranteed_amount
            # guarantor.save(update_fields=["committed_amount"])

            # Auto-ready if fully covered
            if loan.is_fully_covered:
                loan.status = "Ready for Submission"
                loan.save(update_fields=["status"])

        return instance


class GuaranteeApprovalDeclineSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=GuaranteeRequest.STATUS_CHOICES, required=True
    )

    class Meta:
        model = GuaranteeRequest
        fields = ("status",)
