from decimal import Decimal
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from dateutil.relativedelta import relativedelta
from dateutil import parser
from datetime import timedelta
from django.db.models import F


import csv
import io
import cloudinary.uploader
from django.http import HttpResponse
from transactions.models import BulkTransactionLog
from loanapplications.models import LoanApplication
from loanapplications.serializers import (
    LoanApplicationSerializer,
    LoanStatusUpdateSerializer,
    AdminLoanApplicationSerializer,
    BulkAdminLoanApplicationSerializer,
    BulkUploadFileSerializer,
)
from loanaccounts.models import LoanAccount
from accounts.permissions import IsSystemAdminOrReadOnly
from loanaccounts.serializers import LoanAccountSerializer
from guaranteerequests.models import GuaranteeRequest
from loanapplications.utils import (
    compute_loan_coverage,
    notify_member_on_loan_submission,
    notify_member_on_loan_status_change,
    send_loan_application_approved_email,
)
from guarantors.models import GuarantorProfile


class LoanApplicationListCreateView(generics.ListCreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        is_admin = self.request.user.is_staff or self.request.user.is_sacco_admin
        serializer.save(
            member=self.request.user, status="Pending", admin_created=is_admin
        )

    def get_queryset(self):
        # is_sacco_admin sees all
        # is_member sees own
        if self.request.user.is_staff or self.request.user.is_sacco_admin:
            return self.queryset
        return self.queryset.filter(member=self.request.user)


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


# TODO: Allow admin to update the application before sending it back to the member. Currently it only allows the admin to update the amount and send, the admin needs to review the application after update then decide whether to mark it as amended or revert it and mark it as amended as was.
class AmendApplicationView(generics.UpdateAPIView):
    """Admin amends the application parameters (Draft/Preview)."""

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

        # Allow updating fields - This will recalculate projection in serializer/model
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class FinalizeAmendmentView(generics.UpdateAPIView):
    """Admin finalizes the amendment and marks it as Amended."""

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
                {"detail": "Amendment note is required to finalize."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.status = "Amended"
        instance.amendment_note = amendment_note
        instance.save(update_fields=["status", "amendment_note"])

        serializer = self.get_serializer(instance)
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

        with transaction.atomic():
            # Check coverage first to determine next status
            coverage = compute_loan_coverage(application)

            total_savings = coverage["total_savings"]
            # Available savings logic (must account for what's already locked by others, though typically 0 for self at this stage)
            committed_other = coverage["committed_self_guarantee"]
            available_self = max(Decimal("0"), total_savings - committed_other)

            needed = (
                application.requested_amount - coverage["total_guaranteed_by_others"]
            )

            # Determine how much self-guarantee to lock
            amount_to_lock = max(Decimal("0"), min(available_self, needed))

            # LOCK FUNDS
            if amount_to_lock > 0:
                try:
                    profile = GuarantorProfile.objects.select_for_update().get(
                        member=application.member
                    )

                    if profile.available_capacity() < amount_to_lock:
                        # Should be covered by available_self logic, but good double check
                        raise ValueError("Insufficient guarantee capacity.")

                    from guarantors.services import update_guarantee_status

                    # Lock funds and update application
                    update_guarantee_status(
                        GuaranteeRequest.objects.create(
                            member=application.member,
                            loan_application=application,
                            guarantor=profile,
                            guaranteed_amount=amount_to_lock,
                            status="Pending",  # status will be updated to Accepted below
                        ),
                        "Accepted",
                    )
                except GuarantorProfile.DoesNotExist:
                    # If they have savings but no profile (unlikely with signals, but handled)
                    pass

            # Update status based on NEW coverage (after locking self-guarantee)
            # Re-compute or just trust logic?
            # Trusting logic: if we locked 'needed', we are covered?
            # If available >= needed, we locked 'needed'.

            # Check if fully covered now
            final_coverage = compute_loan_coverage(application)

            if final_coverage["is_fully_covered"]:
                application.status = "Ready for Submission"
                # application.can_submit = True  # This is a property/method, not a DB field
            else:
                application.status = "In Progress"

            application.save(update_fields=["status"])

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
            from guarantors.services import release_guarantees_for_application

            release_guarantees_for_application(application)

            application.status = "Cancelled"
            application.save(update_fields=["status"])

        if application.member.email:
            notify_member_on_loan_status_change(application)
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

        serializer = self.get_serializer(application)

        if application.member.email:
            notify_member_on_loan_submission(application)

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
                    projection_snapshot=instance.projection_snapshot,
                    processing_fee=instance.processing_fee,
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
                from guarantors.services import release_guarantees_for_application

                release_guarantees_for_application(instance)

                instance.status = "Declined"
                instance.save(update_fields=["status"])
                serializer.save(status="Declined")

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        instance = self.get_object()

        if instance.member.email:
            if instance.status == "Approved" and self.loan_account:
                send_loan_application_approved_email(instance, self.loan_account)
            else:
                notify_member_on_loan_status_change(instance)

        data = {
            "detail": f"Application {instance.status.lower()}.",
            "application": LoanApplicationSerializer(instance).data,
        }
        if hasattr(self, "loan_account") and self.loan_account:
            data["loan_account"] = LoanAccountSerializer(self.loan_account).data

        return Response(data, status=status.HTTP_200_OK)


class AdminLoanApplicationTemplateDownloadView(generics.GenericAPIView):
    """Admin downloads the CSV template for bulk loan onboarding."""

    queryset = LoanApplication.objects.all()
    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="loan_application_bulk_template.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(
            [
                "Member No",
                "Member Name",
                "Product Name",
                "Requested Amount",
                "Calculation Mode",
                "Term Months",
                "Monthly Payment",
                "Start Date",
            ]
        )

        from django.contrib.auth import get_user_model

        User = get_user_model()
        members = User.objects.filter(is_member=True, is_active=True).order_by(
            "member_no"
        )

        for member in members:
            parts = filter(
                None, [member.first_name, member.middle_name, member.last_name]
            )
            full_name = " ".join(parts).strip()
            writer.writerow(
                [
                    member.member_no,
                    full_name,
                    "",  # Product Name
                    "",  # Requested Amount
                    "",  # Calculation Mode
                    "",  # Term Months
                    "",  # Monthly Payment
                    "",  # Start Date
                ]
            )

        return response


class BulkAdminLoanApplicationUploadView(generics.GenericAPIView):
    """Admin uploads CSV for bulk loan onboarding (Partial Success)."""

    queryset = LoanApplication.objects.all()
    serializer_class = BulkUploadFileSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data["file"]

        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            return Response(
                {"detail": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Upload to Cloudinary for audit
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                folder="bulk_onboarding/loans",
                format="csv",
            )
            cloudinary_url = upload_result.get("secure_url", "")

            required_cols = [
                "Member No",
                "Product Name",
                "Requested Amount",
                "Calculation Mode",
                "Term Months",
                "Monthly Payment",
                "Start Date",
            ]
            if not reader.fieldnames:
                return Response(
                    {"detail": "File is empty or missing headers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for col in required_cols:
                if col not in reader.fieldnames:
                    return Response(
                        {"detail": f"Missing column: {col}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            success_count = 0
            error_count = 0
            results = []

            for index, row in enumerate(reader, 1):
                try:
                    product_str = str(row.get("Product Name", "")).strip()
                    amount_str = str(row.get("Requested Amount", "")).strip()

                    # Skip rows that the admin left blank
                    if not product_str and not amount_str:
                        continue

                    with transaction.atomic():
                        # Extract strings carefully for possible empty cells
                        term_months_str = str(row.get("Term Months", "")).strip()
                        monthly_payment_str = str(
                            row.get("Monthly Payment", "")
                        ).strip()

                        start_date_str = row.get("Start Date", "").strip()
                        formatted_start_date = None
                        if start_date_str:
                            try:
                                # parser.parse is very flexible with formats (MDY, DMY, YMD)
                                parsed_date = parser.parse(start_date_str)
                                formatted_start_date = parsed_date.strftime("%Y-%m-%d")
                            except (ValueError, TypeError):
                                # If parsing fails, pass original string to let serializer handle it
                                formatted_start_date = start_date_str

                        data = {
                            "member": str(row.get("Member No", "")).strip(),
                            "product": str(row.get("Product Name", "")).strip(),
                            "requested_amount": row.get("Requested Amount", "").strip()
                            or None,
                            "calculation_mode": row.get("Calculation Mode", "").strip()
                            or None,
                            "term_months": (
                                int(term_months_str) if term_months_str else None
                            ),
                            "monthly_payment": (
                                monthly_payment_str if monthly_payment_str else None
                            ),
                            "repayment_frequency": "monthly",
                            "start_date": formatted_start_date,
                        }

                        item_serializer = AdminLoanApplicationSerializer(
                            data=data, context={"request": request}
                        )
                        if item_serializer.is_valid():
                            item_serializer.save()
                            success_count += 1
                            results.append({"row": index, "status": "Success"})
                        else:
                            error_count += 1
                            results.append(
                                {
                                    "row": index,
                                    "status": "Error",
                                    "errors": item_serializer.errors,
                                }
                            )
                except Exception as e:
                    error_count += 1
                    results.append({"row": index, "status": "Error", "error": str(e)})

            # Log to BulkTransactionLog
            BulkTransactionLog.objects.create(
                admin=request.user,
                file_name=file.name,
                cloudinary_url=cloudinary_url,
                transaction_type="Loan Application Onboarding",
                success_count=success_count,
                error_count=error_count,
                reference_prefix="LA-BULK",
            )

            return Response(
                {
                    "detail": "Data processed successfully.",
                    "success_count": success_count,
                    "error_count": error_count,
                    "results": results,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"detail": f"Processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BulkAdminLoanApplicationCreateView(generics.GenericAPIView):
    """Admin creates loan applications in bulk from JSON (Partial Success)."""

    queryset = LoanApplication.objects.all()
    serializer_class = BulkAdminLoanApplicationSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def post(self, request):
        applications_data = request.data.get("applications", [])
        if not isinstance(applications_data, list):
            return Response(
                {"detail": "Expected a list of applications."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success_count = 0
        error_count = 0
        results = []

        for index, data in enumerate(applications_data):
            try:
                with transaction.atomic():
                    item_serializer = AdminLoanApplicationSerializer(
                        data=data, context={"request": request}
                    )
                    if item_serializer.is_valid():
                        item_serializer.save()
                        success_count += 1
                        results.append({"index": index, "status": "Success"})
                    else:
                        error_count += 1
                        results.append(
                            {
                                "index": index,
                                "status": "Error",
                                "errors": item_serializer.errors,
                            }
                        )
            except Exception as e:
                error_count += 1
                results.append({"index": index, "status": "Error", "error": str(e)})

        return Response(
            {
                "detail": "Batch processed successfully.",
                "success_count": success_count,
                "error_count": error_count,
                "results": results,
            },
            status=status.HTTP_201_CREATED,
        )


# Admin creates a loan application for a member
class AdminCreateLoanApplicationView(generics.CreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = AdminLoanApplicationSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
