import logging
import csv
import io
import cloudinary.uploader
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from datetime import date
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from feetypes.models import FeeType
from feetypes.serializers import (
    FeeTypeSerializer,
    BulkFeeTypeSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from feeaccounts.models import FeeAccount
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)

User = get_user_model()


class FeeTypeListCreateView(generics.ListCreateAPIView):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        # create Fee Accounts for all members if is_everyone = True
        fee_type = serializer.save()
        members = User.objects.filter(is_member=True)
        created_accounts = []

        if fee_type.is_everyone:
            for member in members:
                if not FeeAccount.objects.filter(
                    member=member, fee_type=fee_type
                ).exists():
                    account = FeeAccount.objects.create(
                        member=member,
                        fee_type=fee_type,
                        outstanding_balance=fee_type.amount,
                    )
                    created_accounts.append(str(account))
            logger.info(
                f"Created {len(created_accounts)} FeeAccount Accounts {', '.join(created_accounts)}"
            )


class FeeTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class FeeTypeTemplateDownloadView(APIView):
    """
    Endpoint to download a CSV template for bulk Fee Type upload.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="fee_types_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            ["Name", "Amount", "GL Account Name", "Is Everyone", "Can Exceed Limit"]
        )
        return response


class BulkFeeTypeUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk Fee Type creation."""

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
        prefix = f"FEE-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Fee Types Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_fee_types/{prefix}_{file.name}",
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
                    amount = row.get("Amount", "0.00").strip()
                    gl_account_name = row.get("GL Account Name", "").strip()
                    is_everyone = row.get("Is Everyone", "False").strip().lower() in (
                        "true",
                        "1",
                        "yes",
                    )
                    can_exceed = row.get(
                        "Can Exceed Limit", "False"
                    ).strip().lower() in ("true", "1", "yes")

                    if not name or not gl_account_name:
                        raise ValueError("Name and GL Account Name are required.")

                    fee_type_data = {
                        "name": name,
                        "amount": amount,
                        "gl_account": gl_account_name,
                        "is_everyone": is_everyone,
                        "can_exceed_limit": can_exceed,
                    }

                    # Use serializer to resolve GL Account but create manually to avoid double-validation
                    temp_serializer = FeeTypeSerializer(data=fee_type_data)
                    if temp_serializer.is_valid():
                        fee_type = FeeType.objects.create(
                            **temp_serializer.validated_data
                        )
                        success_count += 1

                        if fee_type.is_everyone:
                            for member in members:
                                if not FeeAccount.objects.filter(
                                    member=member, fee_type=fee_type
                                ).exists():
                                    FeeAccount.objects.create(
                                        member=member,
                                        fee_type=fee_type,
                                        outstanding_balance=fee_type.amount,
                                    )
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "name": name,
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


class BulkFeeTypeCreateView(generics.CreateAPIView):
    """Bulk creation of Fee Types via JSON payload."""

    serializer_class = BulkFeeTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        fee_types_data = serializer.validated_data.get("fee_types", [])
        admin = self.request.user
        today = date.today()
        prefix = f"FEE-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin, transaction_type="Fee Types Bulk JSON", reference_prefix=prefix
        )

        success_count = 0
        error_count = 0
        errors = []
        members = User.objects.filter(is_member=True)

        with transaction.atomic():
            for index, fee_data in enumerate(fee_types_data, 1):
                try:
                    fee_type = FeeType.objects.create(**fee_data)
                    success_count += 1

                    if fee_type.is_everyone:
                        for member in members:
                            if not FeeAccount.objects.filter(
                                member=member, fee_type=fee_type
                            ).exists():
                                FeeAccount.objects.create(
                                    member=member,
                                    fee_type=fee_type,
                                    outstanding_balance=fee_type.amount,
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
