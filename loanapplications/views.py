from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from loanapplications.models import LoanApplication
from loanapplications.serializers import (
    LoanApplicationSerializer,
    LoanStatusUpdateSerializer,
)
from loanaccounts.models import LoanAccount
from accounts.permissions import IsSystemAdminOrReadOnly


class LoanApplicationListCreateView(generics.ListCreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)


class LoanApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class SubmitLoanApplicationView(generics.GenericAPIView):
    """
    Submits a loan application if it's in 'Ready for Submission' state.
    """

    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()

        # Only owner can submit
        if application.member != request.user:
            return Response(
                {"detail": "You can only submit your own applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Must be Ready for Submission
        if application.status != "Ready for Submission":
            return Response(
                {"detail": "Application is not ready for submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent double submission
        if application.status == "Submitted":
            return Response(
                {"detail": "Application already submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Submit
        application.status = "Submitted"
        application.save(update_fields=["status"])

        serializer = self.get_serializer(application)
        return Response(
            {
                "detail": "Loan application submitted successfully.",
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


"""
SACCO Admin Views
"""


class ApproveOrDeclineLoanApplicationView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/loanapplications/<reference>/status/  → Admin views any application
    PATCH /api/v1/loanapplications/<reference>/status/ → Approve/Decline (only if Submitted)
    """

    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    # Use different serializers for GET vs PATCH
    def get_serializer_class(self):
        if self.request.method == "GET":
            return LoanApplicationSerializer
        return LoanStatusUpdateSerializer

    def get_queryset(self):
        # Admin can see ALL applications
        return super().get_queryset()

    def perform_update(self, serializer):
        instance = serializer.instance
        new_status = serializer.validated_data.get("status")

        if not new_status:
            raise serializers.ValidationError({"status": "This field is required."})

        if new_status not in ["Approved", "Declined"]:
            raise serializers.ValidationError(
                {"status": "Status must be 'Approved' or 'Declined'."}
            )

        if instance.status != "Submitted":
            raise serializers.ValidationError(
                {
                    "status": f"Cannot {new_status.lower()} an application in '{instance.status}' state."
                }
            )

        # --- Auto-create LoanAccount on Approval ---
        if new_status == "Approved":
            with transaction.atomic():
                LoanAccount.objects.create(
                    member=instance.member,
                    product=instance.product,
                    principal=instance.requested_amount,
                    outstanding_balance=instance.requested_amount,
                    start_date=instance.start_date,
                    status="Active",
                )
                serializer.save(status=new_status)
        else:
            serializer.save(status=new_status)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()

        return Response(
            {
                "detail": f"Application {instance.status.lower()}.",
                "application": LoanApplicationSerializer(instance).data,
            },
            status=status.HTTP_200_OK,
        )
