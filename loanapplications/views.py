from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from dateutil.relativedelta import relativedelta
from datetime import timedelta

from loanapplications.models import LoanApplication
from loanapplications.serializers import (
    LoanApplicationSerializer,
    LoanStatusUpdateSerializer,
)
from loanaccounts.models import LoanAccount
from accounts.permissions import IsSystemAdminOrReadOnly
from loanaccounts.serializers import LoanAccountSerializer
from guaranteerequests.models import GuaranteeRequest
from loanapplications.utils import compute_loan_coverage
from guarantors.models import GuarantorProfile


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
        if (
            application.status != "Ready for Submission"
            and application.status != "Submitted"
        ):
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

        # Compute loan coverage
        coverage = compute_loan_coverage(application)

        # Submit
        application.status = "Submitted"
        application.save(update_fields=["status"])

        # AUTO-CREATE SELF-GUARANTEE IF FULLY SELF COVERED
        if coverage["is_fully_covered"] and coverage["total_guaranteed_by_others"] == 0:
            try:
                guarantor_profile = GuarantorProfile.objects.get(
                    member=application.member
                )
                GuaranteeRequest.objects.create(
                    member=application.member,
                    loan_application=application,
                    guarantor=guarantor_profile,
                    guaranteed_amount=application.requested_amount,
                    status="Accepted",
                )
                # update self_guaranteed_amount
                application.self_guaranteed_amount = application.requested_amount
                application.save(update_fields=["self_guaranteed_amount"])
            except GuarantorProfile.DoesNotExist:
                return Response(
                    {
                        "detail": "Unable to create self-guarantee. Please add guarantor profile."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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

        # Calculate end date
        end_date = instance.start_date
        if instance.repayment_frequency == "monthly":
            end_date += relativedelta(months=instance.term_months)
        elif instance.repayment_frequency == "weekly":
            end_date += timedelta(weeks=instance.term_months * 4.345)

        loan_account = None
        # --- Auto-create LoanAccount on Approval ---
        if new_status == "Approved":
            with transaction.atomic():
                loan_account = LoanAccount.objects.create(
                    member=instance.member,
                    product=instance.product,
                    application=instance,
                    principal=instance.requested_amount,
                    outstanding_balance=instance.projection_snapshot["total_repayment"],
                    start_date=instance.start_date,
                    last_interest_calulation=instance.start_date,
                    status="Active",
                    total_interest_accrued=instance.projection_snapshot[
                        "total_interest"
                    ],
                    end_date=end_date,
                )
                serializer.save(status=new_status)

                instance.loan_account = loan_account
        else:
            serializer.save(status=new_status)

        self.loan_account = loan_account

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()

        data = {
            "detail": f"Application {instance.status.lower()}.",
            "application": LoanApplicationSerializer(instance).data,
        }

        if hasattr(self, "loan_account") and self.loan_account:
            data["loan_account"] = LoanAccountSerializer(self.loan_account).data

        return Response(
            data,
            status=status.HTTP_200_OK,
        )
