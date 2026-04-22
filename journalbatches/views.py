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

from journalbatches.models import JournalBatch
from journalentries.models import JournalEntry
from glaccounts.models import GLAccount
from journalbatches.serializers import (
    JournalBatchSerializer,
    BulkJournalBatchSerializer,
    BulkUploadFileSerializer,
)
from accounts.permissions import IsSystemAdminOrReadOnly
from transactions.models import BulkTransactionLog

logger = logging.getLogger(__name__)


class JournalBatchListCreateView(generics.ListCreateAPIView):
    queryset = JournalBatch.objects.all().prefetch_related("entries")
    serializer_class = JournalBatchSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class JournalBatchDetailView(generics.RetrieveUpdateAPIView):
    queryset = JournalBatch.objects.all().prefetch_related("entries")
    serializer_class = JournalBatchSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"


class JournalBatchTemplateDownloadView(APIView):
    """
    Download a CSV template for bulk journal entry/batch upload.
    Identifier column is used to group multiple rows into a single balanced batch.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="journal_batches_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Batch Identifier",
                "Batch Description",
                "GL Account Name",
                "Debit",
                "Credit",
            ]
        )

        # Add an example row
        writer.writerow(
            ["B001", "Opening Balance Adjustment", "CASH AT BANK", "1000.00", "0.00"]
        )
        writer.writerow(
            ["B001", "Opening Balance Adjustment", "MEMBER SAVINGS", "0.00", "1000.00"]
        )

        return response


class BulkJournalBatchUploadView(generics.CreateAPIView):
    """
    Upload CSV for one or more Journal Batches.
    Rows sharing the same 'Batch Identifier' are grouped into one JournalBatch.
    Each group MUST be balanced (sum debits == sum credits).
    """

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
            rows = list(reader)
        except Exception as e:
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        prefix = f"JOURNAL-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Journal Batches Upload",
            reference_prefix=prefix,
            file_name=file.name,
        )

        # Cloudinary Log
        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_journals/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")

        # Grouping by Identifier
        batches_data = {}
        for index, row in enumerate(rows, 1):
            bid = row.get("Batch Identifier", f"UNNAMED-{index}")
            if bid not in batches_data:
                batches_data[bid] = {
                    "description": row.get("Batch Description", "Manual Bulk Entry"),
                    "entries": [],
                }

            batches_data[bid]["entries"].append(
                {
                    "account": row.get("GL Account Name"),
                    "debit": row.get("Debit") or "0",
                    "credit": row.get("Credit") or "0",
                    "row_index": index,
                }
            )

        success_count = 0
        error_count = 0
        errors = []

        # Process each group
        for bid, bdata in batches_data.items():
            try:
                # 1. Validate Balance
                total_debit = sum(Decimal(e["debit"]) for e in bdata["entries"])
                total_credit = sum(Decimal(e["credit"]) for e in bdata["entries"])

                if total_debit != total_credit:
                    error_count += 1
                    errors.append(
                        {
                            "batch_identifier": bid,
                            "error": f"Unbalanced Batch: Total Debit ({total_debit}) does not equal Total Credit ({total_credit})",
                        }
                    )
                    continue

                if total_debit == 0 and total_credit == 0:
                    error_count += 1
                    errors.append(
                        {
                            "batch_identifier": bid,
                            "error": "Batch has zero total movement.",
                        }
                    )
                    continue

                # 2. Save Batch and Entries Atomically
                with transaction.atomic():
                    batch = JournalBatch.objects.create(
                        description=bdata["description"],
                        posted=True
                    )

                    for e in bdata["entries"]:
                        gl_acc = GLAccount.objects.get(name=e["account"])
                        JournalEntry.objects.create(
                            batch=batch,
                            account=gl_acc,
                            debit=Decimal(e["debit"]),
                            credit=Decimal(e["credit"]),
                            created_by=admin,
                        )

                    success_count += 1

            except GLAccount.DoesNotExist:
                error_count += 1
                errors.append(
                    {
                        "batch_identifier": bid,
                        "error": "One or more GL Account(s) not found.",
                    }
                )
            except Exception as e:
                error_count += 1
                errors.append({"batch_identifier": bid, "error": str(e)})

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


class BulkJournalBatchCreateView(generics.CreateAPIView):
    """
    Bulk create Journal Batches via JSON.
    Expects nested structure: {"description": "...", "entries": [{"account": "...", "debit": 0, "credit": 0}, ...]}
    Each batch MUST be balanced.
    """

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkJournalBatchSerializer

    def post(self, request, *args, **kwargs):
        # We handle either a single batch object or a list of batch objects
        data_list = request.data if isinstance(request.data, list) else [request.data]

        admin = request.user
        today = date.today()
        prefix = f"JOURNAL-BULK-JSON-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Journal Batches JSON",
            reference_prefix=prefix,
        )

        success_count = 0
        error_count = 0
        errors = []

        for index, bdata in enumerate(data_list, 1):
            try:
                serializer = BulkJournalBatchSerializer(data=bdata)
                if serializer.is_valid():
                    v_data = serializer.validated_data
                    entries = v_data["entries"]

                    # Balance check
                    total_debit = sum(e["debit"] for e in entries)
                    total_credit = sum(e["credit"] for e in entries)

                    if total_debit != total_credit:
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"Unbalanced: DR({total_debit}) != CR({total_credit})",
                            }
                        )
                        continue

                    with transaction.atomic():
                        batch = JournalBatch.objects.create(
                            description=v_data.get("description", "JSON Bulk Batch"),
                            reference=v_data.get("reference"),
                            posted=True
                        )
                        for e in entries:
                            JournalEntry.objects.create(
                                batch=batch,
                                account=e["account"],
                                debit=e["debit"],
                                credit=e["credit"],
                                created_by=admin,
                            )
                        success_count += 1
                else:
                    error_count += 1
                    errors.append({"index": index, "errors": serializer.errors})
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
