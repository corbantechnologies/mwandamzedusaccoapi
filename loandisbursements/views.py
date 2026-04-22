import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from loandisbursements.models import LoanDisbursement
from loandisbursements.serializers import (
    LoanDisbursementSerializer,
    BulkLoanDisbursementSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from loandisbursements.utils import send_disbursement_made_email
from loandisbursements.services import process_loan_disbursement_accounting
from transactions.models import BulkTransactionLog
from loanaccounts.models import LoanAccount

logger = logging.getLogger(__name__)


class LoanDisbursementListCreateView(generics.ListCreateAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            disbursement = serializer.save(disbursed_by=self.request.user)
            # Update the loan application status to Disbursed
            loan_application = disbursement.loan_account.application
            loan_application.status = "Disbursed"
            loan_application.save()

            # Process the loan disbursement accounting
            process_loan_disbursement_accounting(disbursement)

            # send email to the account owner if they have an email
            account_owner = disbursement.loan_account.member
            if account_owner.email:
                send_disbursement_made_email(account_owner, disbursement)


class LoanDisbursementDetailView(generics.RetrieveAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"


class LoanDisbursementTemplateDownloadView(APIView):
    """
    Endpoint to download a pre-filled CSV template for bulk Loan Disbursements.
    Lists all Loan Accounts where the related application is "Approved" but not "Disbursed".
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="loan_disbursements_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            ["Member Name", "Loan Account Number", "Principal Amount", "Payment Method"]
        )

        # Filter accounts linked to Approved (but not yet Disbursed) applications
        pending_disbursements = LoanAccount.objects.filter(
            application__status="Approved"
        ).select_related("member", "product")

        for acc in pending_disbursements:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.account_number,
                    acc.principal,
                    "",  # Payment Method
                ]
            )

        return response


class BulkLoanDisbursementUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Loan Disbursements."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkUploadFileSerializer

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        prefix = f"LOAN-DISB-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Disbursements Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_disbursements/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    acc_num = row.get("Loan Account Number")
                    amount_str = row.get("Principal Amount")
                    payment_method = row.get("Payment Method") or None

                    if not acc_num or not amount_str:
                        continue

                    # Prep data for standard serializer
                    disb_data = {
                        "loan_account": acc_num,
                        "amount": amount_str,
                        "payment_method": payment_method,
                        "transaction_status": "Completed",
                        "disbursement_type": "Principal",
                    }

                    serializer = LoanDisbursementSerializer(data=disb_data)
                    if serializer.is_valid():
                        disbursement = serializer.save(disbursed_by=admin)

                        # Trigger Business Logic (copied from standard view for consistency)
                        loan_application = disbursement.loan_account.application
                        loan_application.status = "Disbursed"
                        loan_application.save()

                        process_loan_disbursement_accounting(disbursement)

                        if disbursement.loan_account.member.email:
                            send_disbursement_made_email(
                                disbursement.loan_account.member, disbursement
                            )

                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "account": acc_num,
                                "errors": serializer.errors,
                            }
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
                "log_reference": log.reference_prefix,
                "cloudinary_url": log.cloudinary_url,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class BulkLoanDisbursementCreateView(generics.CreateAPIView):
    """Bulk Loan Disbursement via JSON payload."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkLoanDisbursementSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admin = request.user
        today = date.today()
        prefix = f"LOAN-DISB-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Disbursements JSON",
            reference_prefix=prefix,
        )

        disbursements_data = serializer.validated_data.get("disbursements", [])
        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, disb_data in enumerate(disbursements_data, 1):
                try:
                    disb_data["transaction_status"] = "Completed"
                    disb_data["disbursement_type"] = "Principal"

                    disbursement = LoanDisbursement.objects.create(
                        **disb_data, disbursed_by=admin
                    )

                    # Trigger Business Logic
                    loan_application = disbursement.loan_account.application
                    loan_application.status = "Disbursed"
                    loan_application.save()

                    process_loan_disbursement_accounting(disbursement)

                    if disbursement.loan_account.member.email:
                        send_disbursement_made_email(
                            disbursement.loan_account.member, disbursement
                        )

                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
                "log_reference": log.reference_prefix,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )
