from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, F
from django.db import transaction
from rest_framework.response import Response

from guaranteerequests.models import GuaranteeRequest
from guaranteerequests.serializers import (
    GuaranteeRequestSerializer,
    GuaranteeApprovalDeclineSerializer,
)
from loanapplications.utils import compute_loan_coverage


class GuaranteeRequestListCreateView(generics.ListCreateAPIView):
    """
    - Member makes a request
    """

    queryset = GuaranteeRequest.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuaranteeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        # both the member and guarantor can see the request
        # guarantors should see requests made to them
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
        return GuaranteeRequest.objects.filter(
            Q(member=self.request.user) | Q(guarantor__member=self.request.user)
        )


class GuaranteeRequestUpdateStatusView(generics.UpdateAPIView):
    serializer_class = GuaranteeRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(guarantor__member=self.request.user)

    def get_serializer(self, *args, **kwargs):
        kwargs["partial"] = True
        serializer = super().get_serializer(*args, **kwargs)
        # Only allow 'status'
        for field in serializer.fields:
            if field != "status":
                serializer.fields[field].read_only = True
        return serializer


class GuaranteeRequestUpdateStatusView(generics.UpdateAPIView):
    """
    PATCH /api/v1/guaranteerequests/<reference>/status/
    Only the guarantor can accept or decline.
    """

    serializer_class = GuaranteeApprovalDeclineSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(guarantor__member=self.request.user)

    def perform_update(self, serializer):
        request = self.request
        new_status = serializer.validated_data["status"]

        if new_status not in ["Accepted", "Declined"]:
            raise serializers.ValidationError(
                {"status": "Status must be 'Accepted' or 'Declined'."}
            )

        instance = self.get_object()

        # Only Pending requests can be updated
        if instance.status != "Pending":
            raise serializers.ValidationError(
                {"status": f"Cannot change status from '{instance.status}'."}
            )

        loan_app = instance.loan_application

        # Loan must not be in final state
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {"status": "Cannot modify guarantees on a finalized loan application."}
            )

        with transaction.atomic():
            instance.status = new_status
            instance.save(update_fields=["status"])

            if new_status == "Accepted":
                # RESERVE in guarantor's profile
                profile = instance.guarantor
                profile.committed_guarantee_amount = (
                    F("committed_guarantee_amount") + instance.guaranteed_amount
                )
                profile.save(update_fields=["committed_guarantee_amount"])

                # Auto-ready if now fully covered
                coverage = compute_loan_coverage(loan_app)
                if coverage["is_fully_covered"]:
                    loan_app.status = "Ready for Submission"
                    loan_app.can_submit = True
                    loan_app.save(update_fields=["status"])
                    loan_app.save(update_fields=["can_submit"])

            # Declined → do nothing (no reservation)

        # Return full request with updated status
        return Response(
            GuaranteeRequestSerializer(
                instance, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )
