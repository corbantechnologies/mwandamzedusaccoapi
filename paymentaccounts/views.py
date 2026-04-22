import csv
import io
import cloudinary.uploader
import logging
from datetime import date

from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from paymentaccounts.models import PaymentAccount
from paymentaccounts.serializers import (
    PaymentAccountSerializer,
    BulkUploadFileSerializer,
    BulkPaymentAccountSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)


class PaymentAccountListCreateView(generics.ListCreateAPIView):
    queryset = PaymentAccount.objects.all()
    serializer_class = PaymentAccountSerializer
    permission_classes = [IsSystemAdminOrReadOnly]


class PaymentAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PaymentAccount.objects.all()
    serializer_class = PaymentAccountSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"

    # you cant delete a PaymentAccount, only deactivate it
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class PaymentAccountTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Payment Accounts upload.
    Notice we use GL Account Name because the serializer uses slug field lookup.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="payment_accounts_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(["Name", "GL Account Name", "Is Active"])
        return response


class BulkPaymentAccountUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Payment Accounts creation."""

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
            logger.error(f"Failed to read CSV: {str(e)}")
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"PAY-BULK-{date_str}"

        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Payment Accounts Upload",
                reference_prefix=prefix,
                success_count=0,
                error_count=0,
                file_name=file.name,
            )
        except Exception as e:
            logger.error(f"Failed to create BulkTransactionLog: {str(e)}")
            return Response(
                {"error": "Failed to initialize transaction log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_payment_accounts/{prefix}_{file.name}",
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
                    name = row.get("Name", "").strip()
                    gl_account_name = row.get("GL Account Name", "").strip()

                    if not name or not gl_account_name:
                        raise ValueError("Name and GL Account Name are required.")

                    is_active_str = row.get("Is Active", "True").strip().lower()
                    is_active = is_active_str in ("true", "1", "yes", "y")

                    payment_data = {
                        "name": name,
                        "gl_account": gl_account_name,  # DRF SlugRelatedField resolves this to the GLAccount
                        "is_active": is_active,
                    }

                    payment_serializer = PaymentAccountSerializer(data=payment_data)
                    if payment_serializer.is_valid():
                        payment_serializer.save()
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "name": name,
                                "error": str(payment_serializer.errors),
                            }
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            try:
                log.success_count = success_count
                log.error_count = error_count
                log.save()
            except Exception as e:
                logger.error(f"Failed to update BulkTransactionLog: {str(e)}")

        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "cloudinary_url": log.cloudinary_url,
        }

        try:
            return Response(
                response_data,
                status=(
                    status.HTTP_201_CREATED
                    if success_count > 0
                    else status.HTTP_400_BAD_REQUEST
                ),
            )
        except Exception as e:
            logger.error(f"Failed to return response: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class BulkPaymentAccountCreateView(generics.CreateAPIView):
    """
    Endpoint for bulk creation of Payment Accounts via JSON array payload.
    """

    serializer_class = BulkPaymentAccountSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        accounts_data = serializer.validated_data.get("accounts", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"PAY-BULK-JSON-{date_str}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Payment Accounts Bulk JSON Create",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, account_data in enumerate(accounts_data, 1):
                try:
                    PaymentAccount.objects.create(**account_data)
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

        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)
