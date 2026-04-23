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

from loanproducts.models import LoanProduct
from loanproducts.serializers import (
    LoanProductSerializer,
    BulkLoanProductSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)


class LoanProductListCreateView(generics.ListCreateAPIView):
    queryset = LoanProduct.objects.all()
    serializer_class = LoanProductSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class LoanProductDetailView(generics.RetrieveUpdateAPIView):
    queryset = LoanProduct.objects.all()
    serializer_class = LoanProductSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"


class LoanProductTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Loan Products upload.
    Notice we use GL Account Name because the serializer uses slug field lookup.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="loan_products_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Name",
                "Interest Method",
                "Interest Rate",
                "Processing Fee",
                "Interest Period",
                "Calculation Schedule",
                "GL Principal Asset",
                "GL Interest Revenue",
                "GL Penalty Revenue",
                "GL Processing Fee Revenue",
                "Is Active",
            ]
        )
        return response


class BulkLoanProductUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Loan Products creation."""

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
        prefix = f"LOANPRODUCT-BULK-{date_str}"

        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Loan Products Upload",
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
                public_id=f"bulk_loan_products/{prefix}_{file.name}",
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

                    if not name:
                        raise ValueError("Name is required.")

                    is_active_str = row.get("Is Active", "True").strip().lower()
                    is_active = is_active_str in ("true", "1", "yes", "y")

                    interest_method = row.get("Interest Method", "Reducing").strip()
                    if "reducing" in interest_method.lower():
                        interest_method = "Reducing"
                    elif "flat" in interest_method.lower():
                        interest_method = "Flat"

                    try:
                        interest_rate = Decimal(
                            row.get("Interest Rate", "0.00").strip()
                        )
                    except Exception:
                        interest_rate = Decimal("0.00")

                    try:
                        processing_fee = Decimal(
                            row.get("Processing Fee", "0.00").strip()
                        )
                    except Exception:
                        processing_fee = Decimal("0.00")

                    interest_period = row.get("Interest Period", "Monthly").strip()
                    calculation_schedule = row.get(
                        "Calculation Schedule", "Fixed"
                    ).strip()

                    gl_principal_asset = (
                        row.get("GL Principal Asset", "").strip() or None
                    )
                    gl_interest_revenue = (
                        row.get("GL Interest Revenue", "").strip() or None
                    )
                    gl_penalty_revenue = (
                        row.get("GL Penalty Revenue", "").strip() or None
                    )
                    gl_processing_fee_revenue = (
                        row.get("GL Processing Fee Revenue", "").strip() or None
                    )

                    product_data = {
                        "name": name,
                        "interest_method": interest_method,
                        "interest_rate": str(interest_rate),
                        "processing_fee": str(processing_fee),
                        "interest_period": interest_period,
                        "calculation_schedule": calculation_schedule,
                        "is_active": is_active,
                        "gl_principal_asset": gl_principal_asset,
                        "gl_interest_revenue": gl_interest_revenue,
                        "gl_penalty_revenue": gl_penalty_revenue,
                        "gl_processing_fee_revenue": gl_processing_fee_revenue,
                    }

                    LoanProduct.objects.create(**product_data)
                    success_count += 1
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


class BulkLoanProductCreateView(generics.CreateAPIView):
    """
    Endpoint for bulk creation of Loan Products via JSON array payload.
    """

    serializer_class = BulkLoanProductSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        products_data = serializer.validated_data.get("loan_products", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"LOANPRODUCT-BULK-JSON-{date_str}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Products Bulk JSON Create",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, product_data in enumerate(products_data, 1):
                try:
                    LoanProduct.objects.create(**product_data)
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
