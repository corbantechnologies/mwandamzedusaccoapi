# guaranteerequests/views.py
from rest_framework import generics, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, F

from guaranteerequests.models import GuaranteeRequest
from savings.models import SavingsAccount
from guaranteerequests.serializers import (
    GuaranteeRequestSerializer,
    GuaranteeApprovalDeclineSerializer,
)
from loanapplications.utils import compute_loan_coverage


class GuaranteeRequestListCreateView(generics.ListCreateAPIView):
    """
    Member creates a guarantee request
    Both member and guarantor can list their requests
    """

    queryset = GuaranteeRequest.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuaranteeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        user = self.request.user
        return (
            super()
            .get_queryset()
            .filter(Q(member=user) | Q(guarantor__member=user))
            .select_related("member", "guarantor__member", "loan_application")
        )


class GuaranteeRequestRetrieveView(generics.RetrieveAPIView):
    serializer_class = GuaranteeRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        user = self.request.user
        return GuaranteeRequest.objects.filter(
            Q(member=user) | Q(guarantor__member=user)
        )


class GuaranteeRequestUpdateStatusView(generics.UpdateAPIView):
    """
    PATCH /guaranteerequests/<reference>/status/
    Only guarantor can accept/decline
    """

    serializer_class = GuaranteeApprovalDeclineSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(guarantor__member=self.request.user)

    def perform_update(self, serializer):
        new_status = serializer.validated_data["status"]
        if new_status not in ["Accepted", "Declined"]:
            raise serializers.ValidationError(
                {"status": "Must be 'Accepted' or 'Declined'."}
            )

        instance = self.get_object()
        if instance.status != "Pending":
            raise serializers.ValidationError({"status": "Request already processed."})

        loan_app = instance.loan_application
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {"status": "Loan application is finalized."}
            )

        with transaction.atomic():
            if new_status == "Accepted":
                profile = instance.guarantor

                # Check for amount adjustment
                adjusted_amount = serializer.validated_data.get("guaranteed_amount")
                amount_to_commit = instance.guaranteed_amount

                if adjusted_amount:
                    amount_to_commit = adjusted_amount
                    instance.guaranteed_amount = amount_to_commit
                    # note: we save instance later

                # Sync max_guarantee_amount to ensure capacity check is fresh
                total_savings = SavingsAccount.objects.filter(
                    member=profile.member
                ).aggregate(total=models.Sum("balance"))["total"] or Decimal("0")
                profile.max_guarantee_amount = total_savings

                # Validate capacity
                if profile.available_capacity() < amount_to_commit:
                    raise serializers.ValidationError(
                        {
                            "guaranteed_amount": f"Insufficient capacity. Available: {profile.available_capacity()}"
                        }
                    )

                profile.committed_guarantee_amount = (
                    F("committed_guarantee_amount") + amount_to_commit
                )
                profile.save(
                    update_fields=["max_guarantee_amount", "committed_guarantee_amount"]
                )

            instance.status = new_status
            instance.save(update_fields=["status", "guaranteed_amount"])

            if new_status == "Accepted":
                coverage = compute_loan_coverage(loan_app)
                if coverage["is_fully_covered"]:
                    loan_app.status = "Ready for Submission"
                    loan_app.save(update_fields=["status"])

        return Response(
            GuaranteeRequestSerializer(
                instance, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )
