from rest_framework import generics, status
import logging
import csv
import io
import cloudinary.uploader
from django.db import transaction
from django.http import HttpResponse
from datetime import date
from rest_framework.response import Response
from rest_framework.views import APIView

from existingloanspayments.models import ExistingLoanPayment
from existingloanspayments.serializers import (
    ExistingLoanPaymentSerializer,
    BulkExistingLoanPaymentSerializer,
    BulkUploadFileSerializer,
)
from existingloanspayments.services import process_existing_loan_payment_accounting
from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog
from existingloans.models import ExistingLoan

logger = logging.getLogger(__name__)


class ExistingLoanPaymentCreateView(generics.ListCreateAPIView):
    queryset = ExistingLoanPayment.objects.all()
    serializer_class = ExistingLoanPaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        # Use a transaction to ensure both DB save and Accounting succeed together
        with transaction.atomic():
            # 1. Save the payment record
            instance = serializer.save(paid_by=self.request.user)

            # 2. Trigger accounting only if status is Completed
            # (Admin payments usually default to Completed,
            # while M-Pesa starts as Pending and is handled in the callback)
            if instance.transaction_status == "Completed":
                process_existing_loan_payment_accounting(instance)


class ExistingLoanPaymentDetailView(generics.RetrieveAPIView):
    queryset = ExistingLoanPayment.objects.all()
    serializer_class = ExistingLoanPaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"


class ExistingLoanPaymentTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Existing Loan Payment upload.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="existing_loan_payments_bulk_template.csv"'

        writer = csv.writer(response)
        writer.writerow(["Loan Account No", "Repayment Type", "Amount", "Payment Method"])
        return response


class BulkExistingLoanPaymentUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Existing Loan Payment creation."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkUploadFileSerializer

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            return Response({"error": f"Invalid CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        admin = request.user
        today = date.today()
        prefix = f"EX-PYMT-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Existing Loan Payments Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_existing_payments/{prefix}_{file.name}",
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
                    loan_acc = row.get("Loan Account No", "").strip()
                    amount = row.get("Amount", "0.00").strip()
                    pmethod = row.get("Payment Method", "").strip()
                    rtype = row.get("Repayment Type", "Regular Repayment").strip()

                    row_data = {
                        "existing_loan": loan_acc,
                        "amount": amount,
                        "payment_method": pmethod,
                        "repayment_type": rtype,
                        "transaction_status": "Completed"
                    }

                    # Use serializer to resolve slugs but create manually to avoid double-validation
                    temp_serializer = ExistingLoanPaymentSerializer(data=row_data)
                    if temp_serializer.is_valid():
                        instance = ExistingLoanPayment.objects.create(
                            **temp_serializer.validated_data,
                            paid_by=admin
                        )
                        process_existing_loan_payment_accounting(instance)
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append({"row": index, "loan": loan_acc, "error": str(temp_serializer.errors)})
                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        return Response({
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "cloudinary_url": log.cloudinary_url
        }, status=status.HTTP_201_CREATED if success_count > 0 else status.HTTP_400_BAD_REQUEST)


class BulkExistingLoanPaymentCreateView(generics.CreateAPIView):
    """Bulk creation of Existing Loan Payments via JSON payload."""

    serializer_class = BulkExistingLoanPaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        payments_data = serializer.validated_data.get("payments", [])
        admin = self.request.user
        today = date.today()
        prefix = f"EX-PYMT-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Existing Loan Payments Bulk JSON",
            reference_prefix=prefix
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, payment_data in enumerate(payments_data, 1):
                try:
                    payment_data["transaction_status"] = "Completed"
                    instance = ExistingLoanPayment.objects.create(
                        **payment_data,
                        paid_by=admin
                    )
                    process_existing_loan_payment_accounting(instance)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            log.success_count = success_count
            log.error_count = error_count
            log.save()

        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
        }

        return Response(response_data, status=status.HTTP_201_CREATED if success_count > 0 else status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)
