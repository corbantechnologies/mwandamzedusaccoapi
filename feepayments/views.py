import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from decimal import Decimal
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.http import HttpResponse

from feepayments.models import FeePayment
from feepayments.serializers import (
    FeePaymentSerializer,
    BulkFeePaymentSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from feepayments.services import process_fee_payment_accounting
from transactions.models import BulkTransactionLog
from feeaccounts.models import FeeAccount

logger = logging.getLogger(__name__)


class FeePaymentListCreateView(generics.ListCreateAPIView):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(paid_by=self.request.user)
            if instance.transaction_status == "Completed":
                process_fee_payment_accounting(instance)


class FeePaymentView(generics.RetrieveAPIView):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"


# TODO: Implement bulk fee payment upload and processing


class FeePaymentTemplateDownloadView(APIView):
    """
    Endpoint to download a pre-filled CSV template for bulk Fee Payments.
    Lists all fee accounts with outstanding balances.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="fee_payments_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Member Name",
                "Fee Type",
                "Fee Account Number",
                "Amount",
                "Payment Method",
            ]
        )

        # Predominantly show accounts that still have balances
        fee_accounts = FeeAccount.objects.filter(
            outstanding_balance__gt=0
        ).select_related("member", "fee_type")

        for acc in fee_accounts:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.fee_type.name,
                    acc.account_number,
                    "",  # Empty Amount
                    "",  # Empty Payment Method
                ]
            )

        return response


class BulkFeePaymentUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Fee Payments."""

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
        prefix = f"FEES-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Fee Payments Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_fees/{prefix}_{file.name}",
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
                    acc_num = row.get("Fee Account Number")
                    amount_str = row.get("Amount")

                    if not acc_num or not amount_str:
                        continue

                    payment_data = {
                        "fee_account": acc_num,
                        "amount": amount_str,
                        "payment_method": row.get("Payment Method"),
                        "transaction_status": "Completed",
                    }

                    serializer = FeePaymentSerializer(data=payment_data)
                    if serializer.is_valid():
                        instance = serializer.save(paid_by=admin)
                        process_fee_payment_accounting(instance)
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


class BulkFeePaymentCreateView(generics.CreateAPIView):
    """Bulk Fee Payment via JSON payload."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkFeePaymentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admin = request.user
        today = date.today()
        prefix = f"FEES-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin, transaction_type="Fee Payments JSON", reference_prefix=prefix
        )

        fee_payments_data = serializer.validated_data.get("fee_payments", [])
        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, payment_data in enumerate(fee_payments_data, 1):
                try:
                    payment_data["transaction_status"] = "Completed"
                    instance = FeePayment.objects.create(**payment_data, paid_by=admin)
                    process_fee_payment_accounting(instance)
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
