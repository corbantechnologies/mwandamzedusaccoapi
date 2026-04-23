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

from existingloans.models import ExistingLoan
from existingloans.serializers import (
    ExistingLoanSerializer,
    BulkExistingLoanSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)


class ExistingLoanListCreateView(generics.ListCreateAPIView):
    """
    List all existing loans.
    """

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = ExistingLoanSerializer
    queryset = ExistingLoan.objects.all()


class ExistingLoanDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve an existing loan by ID.
    """

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = ExistingLoanSerializer
    queryset = ExistingLoan.objects.all()
    lookup_field = "reference"


class ExistingLoanTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Existing Loan upload.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="existing_loans_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Member No",
                "Principal",
                "GL Principal Asset",
                "GL Penalty Revenue",
                "GL Interest Revenue",
                "Status",
                "Payment Method",
                "Total Amount Paid",
                "Total Interest Paid",
                "Total Penalties Paid",
            ]
        )
        return response


class BulkExistingLoanUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Existing Loan creation."""

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
        prefix = f"EX-LOAN-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Existing Loans Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_existing_loans/{prefix}_{file.name}",
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
                    member_no = row.get("Member No", "").strip()
                    principal = row.get("Principal", "0.00").strip()
                    gl_p = row.get("GL Principal Asset", "").strip()
                    gl_pen = row.get("GL Penalty Revenue", "").strip()
                    gl_int = row.get("GL Interest Revenue", "").strip()
                    status_val = row.get("Status", "Active").strip()
                    pay_method = row.get("Payment Method", "").strip()
                    total_paid = row.get("Total Amount Paid", "0.00").strip()
                    total_int_paid = row.get("Total Interest Paid", "0.00").strip()
                    total_pen_paid = row.get("Total Penalties Paid", "0.00").strip()

                    row_data = {
                        "member": member_no,
                        "principal": principal,
                        "gl_principal_asset": gl_p,
                        "gl_penalty_revenue": gl_pen,
                        "gl_interest_revenue": gl_int,
                        "status": status_val,
                        "payment_method": pay_method,
                        "total_amount_paid": total_paid,
                        "total_interest_paid": total_int_paid,
                        "total_penalties_paid": total_pen_paid,
                    }

                    # Use serializer to resolve slugs but create manually to avoid double-validation
                    temp_serializer = ExistingLoanSerializer(data=row_data)
                    if temp_serializer.is_valid():
                        ExistingLoan.objects.create(**temp_serializer.validated_data)
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "member": member_no,
                                "error": str(temp_serializer.errors),
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


class BulkExistingLoanCreateView(generics.CreateAPIView):
    """Bulk creation of Existing Loans via JSON payload."""

    serializer_class = BulkExistingLoanSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        loans_data = serializer.validated_data.get("loans", [])
        admin = self.request.user
        today = date.today()
        prefix = f"EX-LOAN-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Existing Loans Bulk JSON",
            reference_prefix=prefix,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, loan_data in enumerate(loans_data, 1):
                try:
                    ExistingLoan.objects.create(**loan_data)
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
