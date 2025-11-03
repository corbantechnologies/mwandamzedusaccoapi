from rest_framework import serializers

from guaranteerequests.models import GuaranteeRequest
from loanapplications.models import LoanApplication
from guarantors.models import GuarantorProfile


class GuaranteeRequestSerializer(serializers.ModelSerializer):
    guarantor = serializers.SlugRelatedField(
        slug_field="member_number",
        queryset=GuarantorProfile.objects.filter(is_eligible=True),
    )
    loan_application = serializers.SlugRelatedField(
        slug_field="reference", queryset=LoanApplication.objects.all()
    )
    status = serializers.ChoiceField(
        read_only=True, choices=GuaranteeRequest.STATUS_CHOICES
    )

    class Meta:
        model = GuaranteeRequest
        fields = (
            "loan_application",
            "guarantor",
            "guaranteed_amount",
            "status",
            "created_at",
            "updated_at",
            "reference",
        )
