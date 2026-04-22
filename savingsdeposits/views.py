import requests
import csv
import io
import cloudinary.uploader
import logging
import threading
import base64
from decimal import Decimal
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.serializers import ValidationError


from accounts.permissions import IsSystemAdminOrReadOnly
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import (
    SavingsDepositSerializer,
    BulkSavingsDepositSerializer,
    BulkUploadFileSerializer,
)
from savingsdeposits.utils import send_deposit_made_email
from datetime import datetime, date
from django.db import transaction, models
from transactions.models import BulkTransactionLog
from savingtypes.models import SavingType
from mpesa.models import MpesaBody
from savings.models import SavingsAccount
from mpesa.utils import get_access_token
from savingsdeposits.services import process_savings_deposit_accounting

logger = logging.getLogger(__name__)


class AdminSavingsDepositCreateView(generics.CreateAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposit = serializer.save(
            deposited_by=self.request.user,
            transaction_status="Completed",
            payment_status="COMPLETED",
            payment_status_description="Admin Deposit",
        )

        # Post to GL and update balances
        process_savings_deposit_accounting(deposit)

        # Send email to the account owner if they have an email address
        account_owner = deposit.savings_account.member
        if account_owner.email:
            send_deposit_made_email(account_owner, deposit)


class SavingsDepositView(generics.RetrieveAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"


"""
Bulk Transactions:
- With JSON payload
- With file upload (CSV)
"""

class BulkSavingsDepositView(generics.CreateAPIView):
    serializer_class = BulkSavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def create(self, request, *args, **kwargs):
        # 1. Intercept raw request data before DRF tries to serialize/validate models
        deposits_data = request.data.get("deposits", [])
        admin = request.user
        prefix = f"SAVINGS-BULK-{date.today().strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Savings Deposits",
            reference_prefix=prefix,
        )

        success_count = 0
        error_count = 0
        errors = []

        for index, raw_data in enumerate(deposits_data, 1):
            try:
                with transaction.atomic():
                    # 2. Clean account number while it is still guaranteed to be a string
                    if "savings_account" in raw_data:
                        raw_data["savings_account"] = self._clean_account_number(
                            raw_data["savings_account"]
                        )

                    # 3. Inject standard operational fields
                    raw_data.update(
                        {
                            "reference": f"{prefix}-{index:04d}",
                            "transaction_status": "Completed",
                            "payment_status": "COMPLETED",
                            "payment_status_description": "Bulk Admin Deposit",
                            "is_active": True,
                        }
                    )

                    if not raw_data.get("payment_method"):
                        raise ValidationError(
                            {
                                "payment_method": "Payment Method is required and must match an existing PaymentAccount name"
                            }
                        )

                    # 4. Validate and save individual deposit
                    serializer = SavingsDepositSerializer(data=raw_data)
                    if not serializer.is_valid():
                        raise ValidationError(serializer.errors)

                    # Note: deposited_by is injected during save(), as passing it into raw_data
                    # doesn't work for read_only fields in the serializer.
                    deposit = serializer.save(deposited_by=admin)

                    # Post to GL and update balance
                    process_savings_deposit_accounting(deposit)

                # Success
                success_count += 1
                logger.info(
                    f"✅ Bulk JSON success: {deposit.reference} | "
                    f"Account: {deposit.savings_account.account_number} | Amount: {deposit.amount}"
                )

                account_owner = deposit.savings_account.member
                if account_owner.email:
                    try:
                        send_deposit_made_email(account_owner, deposit)
                    except Exception as e:
                        logger.warning(f"Email failed for {deposit.reference}: {e}")

            except Exception as e:
                error_count += 1
                errors.append(
                    {
                        "index": index,
                        "account_sent": raw_data.get("savings_account"),
                        "amount": raw_data.get("amount"),
                        "error": str(e),
                    }
                )
                logger.error(
                    f"❌ Bulk JSON failed at index {index}: {str(e)}", exc_info=True
                )

        log.success_count = success_count
        log.error_count = error_count
        log.save()

        # 5. Safely return our custom response structure
        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors[:30],
                "log_reference": log.reference_prefix,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    def _clean_account_number(self, value):
        """Extract clean account number from full __str__ or normal value"""
        if not value:
            return value
        if isinstance(value, str):
            # Handle "S2631720742 - SCS001 - Dalienst - Fixed Deposit"
            cleaned = value.split("-")[0].strip()
            cleaned = cleaned.split()[0].strip()  # In case of spaces
            return cleaned
        return str(value).strip()


class BulkSavingsDepositUploadView(generics.CreateAPIView):
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
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            logger.error(f"CSV read error: {e}")
            return Response(
                {"error": f"Invalid CSV: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )

        savings_types = list(SavingType.objects.all().values_list("name", flat=True))
        admin = request.user
        prefix = f"SAVINGS-BULK-{date.today().strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Savings Deposits",
            reference_prefix=prefix,
            file_name=file.name,
        )

        # Cloudinary backup
        try:
            upload_result = cloudinary.uploader.upload(
                io.StringIO(csv_content),
                resource_type="raw",
                public_id=f"bulk_savings/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result.get("secure_url")
            log.save()
        except Exception as e:
            logger.warning(f"Cloudinary upload failed: {e}")

        success_count = 0
        error_count = 0
        errors = []

        for index, row in enumerate(reader, 1):
            try:
                deposit_dicts = self._parse_row(row, savings_types)

                if not deposit_dicts:
                    error_count += 1
                    errors.append(
                        {"row": index, "error": "No valid deposit data found in row"}
                    )
                    continue

                for data in deposit_dicts:
                    with transaction.atomic():
                        # Removed "deposited_by" from here—DRF strips read_only fields from dictionaries
                        data.update(
                            {
                                "reference": f"{prefix}-{index:04d}",
                                "transaction_status": "Completed",
                                "payment_status": "COMPLETED",
                                "payment_status_description": "Bulk Upload Deposit",
                                "is_active": True,
                            }
                        )

                        if not data.get("payment_method"):
                            raise ValidationError(
                                {
                                    "payment_method": "Payment Method is required. Must match a valid PaymentAccount name"
                                }
                            )

                        serializer = SavingsDepositSerializer(data=data)
                        if not serializer.is_valid():
                            raise ValidationError(serializer.errors)

                        # Pass the admin explicitly to the save method
                        deposit = serializer.save(deposited_by=admin)

                        process_savings_deposit_accounting(deposit)

                    success_count += 1
                    logger.info(
                        f"✅ Bulk CSV success - Row {index}: {deposit.reference} | "
                        f"Account: {deposit.savings_account.account_number} | Amount: {deposit.amount}"
                    )

                    if deposit.savings_account.member.email:
                        try:
                            send_deposit_made_email(
                                deposit.savings_account.member, deposit
                            )
                        except Exception as e:
                            logger.warning(f"Email failed: {deposit.reference}")

            except Exception as e:
                error_count += 1
                errors.append(
                    {
                        "row": index,
                        "account_sent": row.get("Account Number"),
                        "error": str(e),
                    }
                )
                logger.error(f"❌ Row {index} failed: {str(e)}", exc_info=True)

        log.success_count = success_count
        log.error_count = error_count
        log.save()

        # Added dynamic status code to match the JSON view behavior
        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors[:30],
                "log_reference": log.reference_prefix,
                "cloudinary_url": log.cloudinary_url,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )

    def _parse_row(self, row: dict, savings_types: list) -> list:
        """Parse row and clean account numbers"""
        deposits = []
        payment_method = row.get("Payment Method")

        # Single-row format
        if row.get("Amount"):
            raw_account = row.get("Account Number") or row.get("savings_account")
            if raw_account:
                clean_account = self._clean_account_number(raw_account)
                try:
                    amount = float(row["Amount"])
                    if amount >= 0.01:
                        deposits.append(
                            {
                                "savings_account": clean_account,
                                "amount": amount,
                                "payment_method": payment_method,
                                "deposit_type": "Individual Deposit",
                                "currency": "KES",
                            }
                        )
                except (ValueError, TypeError):
                    pass

        # Multi-type format
        else:
            for stype in savings_types:
                amt_key = f"{stype} Amount"
                acc_key = f"{stype} Account"
                if row.get(amt_key) and row.get(acc_key):
                    try:
                        amount = float(row[amt_key])
                        if amount >= 0.01:
                            clean_account = self._clean_account_number(row[acc_key])
                            deposits.append(
                                {
                                    "savings_account": clean_account,
                                    "amount": amount,
                                    "payment_method": payment_method,
                                    "deposit_type": "Individual Deposit",
                                    "currency": "KES",
                                }
                            )
                    except (ValueError, TypeError):
                        continue

        return deposits

    def _clean_account_number(self, value):
        """Extract only the account number part"""
        if not value:
            return value
        if isinstance(value, str):
            # Remove everything after first '-' or space
            cleaned = value.split("-")[0].strip()
            cleaned = cleaned.split()[0].strip()
            return cleaned
        return str(value).strip()


"""
M-Pesa Integration
This is different
The posting to ledger is done in the callback url
"""


class SavingsDepositListCreateView(generics.ListCreateAPIView):
    """
    Members create a savings deposit instance which defaults to Pending and PENDING
    Then proceed to M-Pesa STK Push
    """

    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(deposited_by=self.request.user)

    def get_queryset(self):
        return SavingsDeposit.objects.filter(deposited_by=self.request.user)


"""
Reconciliation View
"""


class AccountingRetryListView(generics.ListAPIView):
    """Lists all deposits that require manual accounting intervention."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = SavingsDepositSerializer

    def get_queryset(self):
        return SavingsDeposit.objects.filter(transaction_status="Completed").filter(
            models.Q(balance_updated=False) | models.Q(posted_to_gl=False)
        )


class ProcessPendingAccountingView(APIView):
    """Endpoint to manually trigger the accounting service for a specific deposit."""

    permission_classes = [IsSystemAdminOrReadOnly]

    def post(self, request, reference):
        try:
            deposit = SavingsDeposit.objects.get(reference=reference)

            # The service handles the check for transaction_status="Completed"
            # and ensures no double-posting occurs via its internal flags.
            success = process_savings_deposit_accounting(deposit)

            if success:
                return Response(
                    {
                        "message": f"Accounting for {deposit.reference} processed successfully."
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Transaction is not in a state to be processed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except SavingsDeposit.DoesNotExist:
            return Response(
                {"error": "Deposit not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SavingsDepositTemplateDownloadView(APIView):
    """
    Endpoint to download a pre-filled CSV template for bulk Savings Deposits upload.
    It lists all active Savings Accounts with Member Name and Saving Type.
    """

    permission_classes = [IsSystemAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="savings_deposits_bulk_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            ["Member Name", "Account Number", "Saving Type", "Amount", "Payment Method"]
        )

        accounts = SavingsAccount.objects.filter(is_active=True).select_related(
            "member", "account_type"
        )
        for acc in accounts:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.account_number,
                    acc.account_type.name,
                    "",  # Empty Amount
                    "",  # Empty Payment Method
                ]
            )

        return response
