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

from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog
from glaccounts.models import GLAccount
from glaccounts.serializers import (
    GLAccountSerializer,
    BulkUploadFileSerializer,
    BulkGLAccountSerializer,
)

logger = logging.getLogger(__name__)


class GLAccountListCreateView(generics.ListCreateAPIView):
    queryset = GLAccount.objects.all().prefetch_related("entries")
    serializer_class = GLAccountSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class GLAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GLAccount.objects.all().prefetch_related("entries")
    serializer_class = GLAccountSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"

    # you cant delete a GLAccount, only deactivate it
    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class GLAccountTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk GL Accounts upload.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="gl_accounts_bulk_template.csv"'
        )

        writer = csv.writer(response)
        # Defining columns without 'Balance' as requested
        writer.writerow(["Name", "Code", "Category", "Is Active", "Is Current Account"])

        return response


class BulkGLAccountUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk GL Accounts creation."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkUploadFileSerializer

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Read CSV
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
        prefix = f"GL-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="GL Accounts Upload",
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

        # Upload to Cloudinary
        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_gl_accounts/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            # Proceed even if Cloudinary fails

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    name = row.get("Name", "").strip()
                    code = row.get("Code", "").strip()
                    category = row.get("Category", "").strip().upper()

                    if not name or not code or not category:
                        raise ValueError("Name, Code, and Category are required.")

                    # Auto-correct common plural typos
                    if category == "EXPENSES":
                        category = "EXPENSE"
                    elif category == "LIABILITIES":
                        category = "LIABILITY"
                    elif category == "ASSETS":
                        category = "ASSET"
                    elif category == "REVENUES":
                        category = "REVENUE"
                    elif category == "EQUITIES":
                        category = "EQUITY"

                    is_active_str = row.get("Is Active", "True").strip().lower()
                    is_active = is_active_str in ("true", "1", "yes", "y")

                    is_current_account_str = (
                        row.get("Is Current Account", "True").strip().lower()
                    )
                    is_current_account = is_current_account_str in (
                        "true",
                        "1",
                        "yes",
                        "y",
                    )

                    gl_data = {
                        "name": name,
                        "code": code,
                        "category": category,
                        "is_active": is_active,
                        "is_current_account": is_current_account,
                    }

                    gl_serializer = GLAccountSerializer(data=gl_data)
                    if gl_serializer.is_valid():
                        gl_serializer.save()
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "name": name,
                                "code": code,
                                "error": str(gl_serializer.errors),
                            }
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

            # Update log
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


class BulkGLAccountCreateView(generics.CreateAPIView):
    """
    Endpoint for bulk creation of GL Accounts via JSON array payload.
    """

    serializer_class = BulkGLAccountSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        accounts_data = serializer.validated_data.get("accounts", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"GL-BULK-JSON-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="GL Accounts Bulk JSON Create",
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
                    # Enforce balance to zero
                    account_data["balance"] = "0.00"

                    # Auto-correct category case and plurals
                    if "category" in account_data and isinstance(
                        account_data["category"], str
                    ):
                        cat = account_data["category"].strip().upper()
                        if cat == "EXPENSES":
                            account_data["category"] = "EXPENSE"
                        elif cat == "LIABILITIES":
                            account_data["category"] = "LIABILITY"
                        elif cat == "ASSETS":
                            account_data["category"] = "ASSET"
                        elif cat == "REVENUES":
                            account_data["category"] = "REVENUE"
                        elif cat == "EQUITIES":
                            account_data["category"] = "EQUITY"
                        else:
                            account_data["category"] = cat

                    GLAccount.objects.create(**account_data)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            # Update log
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

    # We override create to return our custom response structure constructed in perform_create
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.perform_create(serializer)
