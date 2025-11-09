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

        if application.status not in ["Ready for Submission", "Submitted"]:
            return Response(
                {"detail": "Application is not ready for submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if application.status == "Submitted":
            return Response(
                {"detail": "Application already submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coverage = compute_loan_coverage(application)

        with transaction.atomic():
            application.status = "Submitted"
            application.save(update_fields=["status"])

            # AUTO SELF-GUARANTEE
            if (
                coverage["is_fully_covered"]
                and coverage["total_guaranteed_by_others"] == 0
            ):
                try:
                    profile = GuarantorProfile.objects.select_for_update().get(
                        member=application.member
                    )

                    # Check & reserve capacity
                    required = application.requested_amount
                    if (
                        profile.committed_guarantee_amount + required
                        > profile.max_guarantee_amount
                    ):
                        raise ValueError("Insufficient guarantee capacity")

                    # RESERVE
                    profile.committed_guarantee_amount += required
                    profile.save(update_fields=["committed_guarantee_amount"])

                    # Create accepted self-guarantee
                    GuaranteeRequest.objects.create(
                        member=application.member,
                        loan_application=application,
                        guarantor=profile,
                        guaranteed_amount=required,
                        status="Accepted",
                    )

                    application.self_guaranteed_amount = required
                    application.save(update_fields=["self_guaranteed_amount"])

                except GuarantorProfile.DoesNotExist:
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
                        profile.committed_guarantee_amount = F('committed_guarantee_amount') - instance.self_guaranteed_amount
                        profile.save(update_fields=['committed_guarantee_amount'])
                    except GuarantorProfile.DoesNotExist:
                        pass
                    instance.self_guaranteed_amount = 0
                    instance.save(update_fields=["self_guaranteed_amount"])

                # Revert external guarantees
                for guarantee in instance.guarantors.filter(status="Accepted"):
                    profile = guarantee.guarantor
                    profile.committed_guarantee_amount = F('committed_guarantee_amount') - guarantee.guaranteed_amount
                    profile.save(update_fields=['committed_guarantee_amount'])
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
