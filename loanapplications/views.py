from decimal import Decimal
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from django.db.models import F


from loanapplications.models import LoanApplication
from loanapplications.serializers import (
    LoanApplicationSerializer,
    LoanStatusUpdateSerializer,
)
from loanaccounts.models import LoanAccount
from savings.models import SavingsAccount
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
        serializer.save(member=self.request.user, status="Pending")


class LoanApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def patch(self, request, *args, **kwargs):
        # Prevent updates if not in editable state
        instance = self.get_object()
        if instance.status not in ["Pending", "In Progress", "Ready for Submission"]:
            # Allow admin to update in certain states? For now restrict.
            if not request.user.is_staff:
                return Response(
                    {
                        "detail": f"Cannot edit application in '{instance.status}' state."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return self.partial_update(request, *args, **kwargs)


class SubmitForAmendmentView(generics.GenericAPIView):
    """Member submits Pending application to Admin for amendment."""

    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()
        if application.member != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if application.status != "Pending":
            return Response(
                {"detail": "Only pending applications can be submitted for amendment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application.status = "Ready for Amendment"
        application.save(update_fields=["status"])
        return Response({"detail": "Application submitted for amendment."})


class AmendApplicationView(generics.UpdateAPIView):
    """Admin amends the application."""

    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != "Ready for Amendment":
            return Response(
                {"detail": "Application is not ready for amendment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amendment_note = request.data.get("amendment_note")
        if not amendment_note:
            return Response(
                {"detail": "Amendment note is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Allow updating fields
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Calculate projection if amounts changed (handled in serializer.update)
        instance = serializer.save()

        instance.status = "Amended"
        instance.amendment_note = amendment_note
        instance.save(update_fields=["status", "amendment_note"])

        return Response(serializer.data)


class AcceptAmendmentView(generics.GenericAPIView):
    """Member accepts the amendments."""

    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()
        if application.member != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if application.status != "Amended":
            return Response(
                {"detail": "Application is not in Amended state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check coverage first to determine next status
        coverage = compute_loan_coverage(application)

        total_savings = coverage["total_savings"]
        committed_other = coverage["committed_self_guarantee"]
        available = max(0, total_savings - committed_other)

        needed = float(application.requested_amount)

        # If we can cover it all with self
        if available >= needed:
            application.self_guaranteed_amount = Decimal(needed)
            application.can_submit = True
            application.status = "Ready for Submission"
        else:
            # Take what we can? Or just 0?
            # Usually we take what we can if the user wants self-guarantee.
            # Let's assume we take what we can.
            application.self_guaranteed_amount = Decimal(available)
            application.status = "In Progress"

        application.save(update_fields=["self_guaranteed_amount", "status"])

        return Response({"detail": f"Amendment accepted. Status: {application.status}"})


class CancelApplicationView(generics.GenericAPIView):
    """Member cancels the application."""

    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()
        if application.member != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)

        if application.status in ["Disbursed", "Cancelled", "Declined"]:
            return Response(
                {"detail": "Cannot cancel this application."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Release self-guarantee if any
            if application.self_guaranteed_amount > 0:
                try:
                    profile = application.member.guarantor_profile
                    profile.committed_guarantee_amount = (
                        F("committed_guarantee_amount")
                        - application.self_guaranteed_amount
                    )
                    profile.save(update_fields=["committed_guarantee_amount"])
                except GuarantorProfile.DoesNotExist:
                    pass
                application.self_guaranteed_amount = 0
                application.save(update_fields=["self_guaranteed_amount"])

            # Release external guarantees if any
            for guarantee in application.guarantors.filter(status="Accepted"):
                profile = guarantee.guarantor
                profile.committed_guarantee_amount = (
                    F("committed_guarantee_amount") - guarantee.guaranteed_amount
                )
                profile.save(update_fields=["committed_guarantee_amount"])
                guarantee.status = "Cancelled"
                guarantee.save(update_fields=["status"])

            application.status = "Cancelled"
            application.save(update_fields=["status"])

        return Response({"detail": "Application cancelled."})


class SubmitLoanApplicationView(generics.GenericAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()

        if application.member != request.user:
            return Response(
                {"detail": "You can only submit your own applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Allow submission from Ready for Submission
        if application.status not in ["Ready for Submission"]:
            return Response(
                {"detail": "Application is not ready for submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Re-check coverage before submission
        coverage = compute_loan_coverage(application)
        if not coverage["is_fully_covered"]:
            return Response(
                {"detail": "Loan is not fully covered. Please add more guarantors."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            application.status = "Submitted"
            application.save(update_fields=["status"])

            # AUTO SELF-GUARANTEE
            # If "available_self" covers the remaining needed, we assume the user WANTS to use it.
            # In fact, coverage calculation logic implies it IS used.
            # We must lock it now.

            # Use available_self calculated from utils
            available_self = coverage["available_self_guarantee"]
            needed = (
                application.requested_amount - coverage["total_guaranteed_by_others"]
            )

            # Amount to lock = min(available, needed)
            # Actually needed can be negative if over-guaranteed by others.
            amount_to_lock = max(Decimal("0"), min(available_self, needed))

            if amount_to_lock > 0:
                try:
                    profile = GuarantorProfile.objects.select_for_update().get(
                        member=application.member
                    )

                    # Double check capacity
                    # Sync with savings first to ensure we have the latest capacity info
                    total_savings = SavingsAccount.objects.filter(
                        member=application.member
                    ).aggregate(total=models.Sum("balance"))["total"] or Decimal("0")
                    profile.max_guarantee_amount = total_savings

                    if profile.available_capacity() < amount_to_lock:
                        raise ValueError(
                            "Insufficient guarantee capacity (savings changed)."
                        )

                    # RESERVE
                    profile.committed_guarantee_amount += amount_to_lock
                    # Saving both fields: max (to persist sync) and committed (to lock)
                    profile.save(
                        update_fields=[
                            "max_guarantee_amount",
                            "committed_guarantee_amount",
                        ]
                    )

                    # Create accepted self-guarantee
                    GuaranteeRequest.objects.create(
                        member=application.member,
                        loan_application=application,
                        guarantor=profile,
                        guaranteed_amount=amount_to_lock,
                        status="Accepted",
                    )

                    application.self_guaranteed_amount = amount_to_lock
                    application.save(update_fields=["self_guaranteed_amount"])

                except GuarantorProfile.DoesNotExist:
                    # Should unlikely happen if they have savings, but possible.
                    application.status = "In Progress"
                    application.save(update_fields=["status"])
                    return Response(
                        {"detail": "Guarantor profile required for self-guarantee."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except ValueError as e:
                    application.status = "In Progress"
                    application.save(update_fields=["status"])
                    return Response(
                        {"detail": str(e)},
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


class ApproveOrDeclineLoanApplicationView(generics.RetrieveUpdateAPIView):
    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    def get_serializer_class(self):
        return (
            LoanApplicationSerializer
            if self.request.method == "GET"
            else LoanStatusUpdateSerializer
        )

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

        end_date = instance.start_date
        if instance.repayment_frequency == "monthly":
            end_date += relativedelta(months=instance.term_months)
        elif instance.repayment_frequency == "weekly":
            end_date += timedelta(weeks=instance.term_months * 4.345)

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
                self.loan_account = loan_account

        else:  # Declined
            with transaction.atomic():
                # Revert self-guarantee
                if instance.self_guaranteed_amount > 0:
                    try:
                        profile = instance.member.guarantor_profile
                        profile.committed_guarantee_amount = (
                            F("committed_guarantee_amount")
                            - instance.self_guaranteed_amount
                        )
                        profile.save(update_fields=["committed_guarantee_amount"])
                    except GuarantorProfile.DoesNotExist:
                        pass
                    instance.self_guaranteed_amount = 0
                    instance.save(update_fields=["self_guaranteed_amount"])

                # Revert external guarantees
                for guarantee in instance.guarantors.filter(status="Accepted"):
                    profile = guarantee.guarantor
                    profile.committed_guarantee_amount = (
                        F("committed_guarantee_amount") - guarantee.guaranteed_amount
                    )
                    profile.save(update_fields=["committed_guarantee_amount"])
                    guarantee.status = "Cancelled"
                    guarantee.save(update_fields=["status"])

                instance.status = "Declined"
                instance.save(update_fields=["status"])
                serializer.save(status="Declined")

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()

        data = {
            "detail": f"Application {instance.status.lower()}.",
            "application": LoanApplicationSerializer(instance).data,
        }
        if hasattr(self, "loan_account") and self.loan_account:
            data["loan_account"] = LoanAccountSerializer(self.loan_account).data

        return Response(data, status=status.HTTP_200_OK)
