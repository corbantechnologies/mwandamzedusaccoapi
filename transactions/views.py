import csv
import io
import asyncio
import cloudinary.uploader
import logging
import calendar
from datetime import date
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.db import transaction
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from datetime import datetime
from collections import defaultdict
from django.db.models import Sum
from rest_framework.views import APIView

from transactions.serializers import AccountSerializer, BulkUploadSerializer
from savings.models import SavingsAccount
from savingtypes.models import SavingType
from ventureaccounts.models import VentureAccount
from loanaccounts.models import LoanAccount
from venturetypes.models import VentureType
from loanproducts.models import LoanProduct
from transactions.models import DownloadLog, BulkTransactionLog

from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import SavingsDepositSerializer
from savingsdeposits.utils import send_deposit_made_email

from venturedeposits.models import VentureDeposit
from venturedeposits.serializers import VentureDepositSerializer
from venturedeposits.utils import send_venture_deposit_made_email

from venturepayments.models import VenturePayment
from venturepayments.serializers import VenturePaymentSerializer
from venturepayments.utils import send_venture_payment_confirmation_email

logger = logging.getLogger(__name__)

User = get_user_model()


class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related(
                "venture_accounts",
                "savings",
                "loan_accounts",
            )
        )


class AccountDetailView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "member_no"

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related(
                "venture_accounts",
                "savings",
                "loan_accounts",
            )
        )


class AccountListDownloadView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related(
                "savings",
                "venture_accounts",
            )
        )

    def get(self, request, *args, **kwargs):
        # load types
        saving_types = list(SavingType.objects.values_list("name", flat=True))
        venture_types = list(VentureType.objects.values_list("name", flat=True))

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        buffer = io.StringIO()

        # ====== FULL ACCOUNT LIST + BULK UPLOAD COLUMNS ======
        headers = ["Member Name", "Member Number"]

        # Savings: Account + Current Balance + Deposit
        for st in saving_types:
            headers += [f"{st} Account", f"{st} Current Balance", f"{st} Deposit"]

        # Ventures: Account + Current Balance + Deposit + Payment
        for vt in venture_types:
            headers += [
                f"{vt} Account",
                f"{vt} Current Balance",
                f"{vt} Deposit",
                f"{vt} Payment",
            ]

        # Optional: Payment Method
        headers += ["Payment Method"]

        # write headers
        writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
        writer.writeheader()

        # write data
        for user in data:
            row = {
                "Member Name": user["member_name"],
                "Member Number": user["member_no"],
                "Payment Method": "Cash",  # default
            }

            # initialize all to empty
            for st in saving_types:
                row[f"{st} Account"] = row[f"{st} Deposit"] = row[
                    f"{st} Current Balance"
                ] = ""

            for vt in venture_types:
                row[f"{vt} Account"] = row[f"{vt} Deposit"] = row[
                    f"{vt} Current Balance"
                ] = row[f"{vt} Payment"] = ""

            # ===== Fill from existing data =====
            # Savings
            for acc_no, acc_type, balance in user["savings_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Current Balance"] = balance
                # Amount column stays empty for bulk upload/edit

            # Ventures
            for acc_no, acc_type, balance in user["venture_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Current Balance"] = balance
                # Amount column stays empty for bulk upload/edit

            # write row
            writer.writerow(row)

        file_name = f"bulk-upload-template-{date.today().strftime('%Y-%m-%d')}.csv"
        cloudinary_path = f"mwandamzedu/bulk-upload-templates/{file_name}"

        # upload to cloudinary
        buffer.seek(0)
        upload_result = cloudinary.uploader.upload(
            buffer, resource_type="raw", public_id=cloudinary_path, format="csv"
        )

        # ==== log ====
        DownloadLog.objects.create(
            admin=request.user,
            file_name=file_name,
            cloudinary_url=upload_result["secure_url"],
        )

        # === Return CSV ===
        buffer.seek(0)
        response = StreamingHttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response


class CombinedBulkUploadView(generics.CreateAPIView):
    """
    Bulk upload accounts: specifically savings, and venture accounts
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BulkUploadSerializer

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

        # Get types
        try:
            saving_types = SavingType.objects.all().values_list("name", flat=True)
            venture_types = VentureType.objects.all().values_list("name", flat=True)
        except Exception as e:
            logger.error(f"Failed to fetch types: {str(e)}")
            return Response(
                {"error": "Failed to fetch account types"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"BULK-UPLOAD-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Combined Bulk Upload",
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
                public_id=f"mwandamzedu/bulk-uploads/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            # Continue even if upload fails, as we want to process the data

        success_count = 0
        error_count = 0
        errors = []

        # Process Rows
        # wrapping in atomic might be risky for large files if we want partial success
        # but safe for consistency. We'll catch per-row exceptions.

        for index, row in enumerate(reader, 1):

            # --- SAVINGS DEPOSITS ---
            for st in saving_types:
                amount_key = f"{st} Deposit"
                account_key = f"{st} Account"

                if row.get(amount_key) and row.get(account_key):
                    try:
                        amount = Decimal(row[amount_key])
                        if amount > 0:
                            data = {
                                "savings_account": row[account_key],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "deposit_type": "Individual Deposit",
                                "transaction_status": "Completed",
                            }
                            serializer = SavingsDepositSerializer(data=data)
                            if serializer.is_valid():
                                deposit = serializer.save(deposited_by=admin)
                                success_count += 1
                                # Email
                                if deposit.savings_account.member.email:
                                    send_deposit_made_email(
                                        deposit.savings_account.member, deposit
                                    )
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Savings {st}",
                                        "error": serializer.errors,
                                    }
                                )
                    except Exception as e:
                        error_count += 1
                        errors.append(
                            {"row": index, "type": f"Savings {st}", "error": str(e)}
                        )

            # --- VENTURE DEPOSITS ---
            for vt in venture_types:
                amount_key = f"{vt} Deposit"
                account_key = f"{vt} Account"

                if row.get(amount_key) and row.get(account_key):
                    try:
                        amount = Decimal(row[amount_key])
                        if amount > 0:
                            data = {
                                "venture_account": row[account_key],
                                "amount": amount,
                                "identity": None,  # let model generate
                            }
                            serializer = VentureDepositSerializer(data=data)
                            if serializer.is_valid():
                                deposit = serializer.save(deposited_by=admin)
                                success_count += 1
                                # Email
                                if deposit.venture_account.member.email:
                                    send_venture_deposit_made_email(
                                        deposit.venture_account.member, deposit
                                    )
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Venture Deposit {vt}",
                                        "error": serializer.errors,
                                    }
                                )
                    except Exception as e:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "type": f"Venture Deposit {vt}",
                                "error": str(e),
                            }
                        )

            # --- VENTURE PAYMENTS ---
            for vt in venture_types:
                payment_key = f"{vt} Payment"
                account_key = f"{vt} Account"

                if row.get(payment_key) and row.get(account_key):
                    try:
                        amount = Decimal(row[payment_key])
                        if amount > 0:
                            data = {
                                "venture_account": row[account_key],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "payment_type": "Individual Settlement",
                                "transaction_status": "Completed",
                            }
                            serializer = VenturePaymentSerializer(data=data)
                            if serializer.is_valid():
                                payment = serializer.save(paid_by=admin)
                                success_count += 1
                                # Email
                                if payment.venture_account.member.email:
                                    send_venture_payment_confirmation_email(
                                        payment.venture_account.member, payment
                                    )
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Venture Payment {vt}",
                                        "error": serializer.errors,
                                    }
                                )
                    except Exception as e:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "type": f"Venture Payment {vt}",
                                "error": str(e),
                            }
                        )

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

        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0 or error_count == 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )
