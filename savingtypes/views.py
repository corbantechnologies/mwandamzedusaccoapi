import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from savingtypes.models import SavingType
from savingtypes.serializers import (
    SavingTypeSerializer,
    BulkSavingTypeSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from savings.models import SavingsAccount
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)

User = get_user_model()


class SavingTypeListCreateView(generics.ListCreateAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)

    def perform_create(self, serializer):
        saving_types = serializer.save()
        members = User.objects.filter(is_member=True)
        created_accounts = []

        for member in members:
            if not SavingsAccount.objects.filter(
                member=member, account_type=saving_types
            ).exists():
                account = SavingsAccount.objects.create(
                    member=member, account_type=saving_types, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccount Accounts {', '.join(created_accounts)}"
        )


class SavingTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"


class SavingTypeTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Saving Types upload.
    Notice we use GL Account Name because the serializer uses slug field lookup.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="saving_types_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            ["Name", "Interest Rate", "GL Account Name", "Can Guarantee", "Is Active"]
        )
        return response


class BulkSavingTypeUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Saving Types creation."""

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
        prefix = f"SAVINGTYPE-BULK-{date_str}"

        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Saving Types Upload",
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
                public_id=f"bulk_saving_types/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")

        success_count = 0
        error_count = 0
        errors = []

        members = User.objects.filter(is_member=True)

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    name = row.get("Name", "").strip()
                    gl_account_name = row.get("GL Account Name", "").strip()
                    interest_rate_str = row.get("Interest Rate", "0.00").strip()

                    if not name or not gl_account_name:
                        raise ValueError("Name and GL Account Name are required.")

                    is_active_str = row.get("Is Active", "True").strip().lower()
                    is_active = is_active_str in ("true", "1", "yes", "y")

                    can_guarantee_str = row.get("Can Guarantee", "True").strip().lower()
                    can_guarantee = can_guarantee_str in ("true", "1", "yes", "y")

                    try:
                        interest_rate = Decimal(interest_rate_str)
                    except Exception:
                        interest_rate = Decimal("0.00")

                    saving_type_data = {
                        "name": name,
                        "interest_rate": str(interest_rate),
                        "gl_account": gl_account_name,  # DRF SlugRelatedField resolves this to the GLAccount
                        "can_guarantee": can_guarantee,
                        "is_active": is_active,
                    }

                    saving_type = SavingType.objects.create(**saving_type_data)
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


class BulkSavingTypeCreateView(generics.CreateAPIView):
    """
    Endpoint for bulk creation of Saving Types via JSON array payload.
    """

    serializer_class = BulkSavingTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        saving_types_data = serializer.validated_data.get("saving_types", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"SAVINGTYPE-BULK-JSON-{date_str}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Saving Types Bulk JSON Create",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        members = User.objects.filter(is_member=True)

        with transaction.atomic():
            for index, saving_type_data in enumerate(saving_types_data, 1):
                try:
                    saving_type = SavingType.objects.create(**saving_type_data)
                    success_count += 1

                    # Create accounts for all members
                    created_accounts = []
                    for member in members:
                        if not SavingsAccount.objects.filter(
                            member=member, account_type=saving_type
                        ).exists():
                            account = SavingsAccount.objects.create(
                                member=member, account_type=saving_type, is_active=True
                            )
                            created_accounts.append(str(account))
                    logger.info(
                        f"Created {len(created_accounts)} Savings Accounts for SavingType: {saving_type.name}"
                    )

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
