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
from django.db.models import Sum, Count
from rest_framework.views import APIView
from django.utils import timezone

from transactions.serializers import AccountSerializer, BulkUploadSerializer
from savings.models import SavingsAccount
from savingtypes.models import SavingType
from loanaccounts.models import LoanAccount
from feetypes.models import FeeType
from loanproducts.models import LoanProduct
from transactions.models import DownloadLog, BulkTransactionLog
from paymentaccounts.models import get_default_payment_method

from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import SavingsDepositSerializer
from savingsdeposits.utils import send_deposit_made_email

from loanpayments.models import LoanPayment
from loandisbursements.models import LoanDisbursement
from playwright.sync_api import sync_playwright
from transactions.reports import (
    get_debtors_report,
    get_balance_sheet,
    get_pnl,
    get_cash_book,
)

from feeaccounts.models import FeeAccount
from feepayments.models import FeePayment
from feepayments.serializers import FeePaymentSerializer
from feepayments.services import process_fee_payment_accounting
from savingsdeposits.services import process_savings_deposit_accounting
from loandisbursements.serializers import LoanDisbursementSerializer
from loandisbursements.services import process_loan_disbursement_accounting
from loandisbursements.utils import send_disbursement_made_email

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
                "fee_accounts",
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
                "fee_accounts",
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
                "fee_accounts",
            )
        )

    def get(self, request, *args, **kwargs):
        # load types
        saving_types = list(SavingType.objects.values_list("name", flat=True))
        fee_types = list(FeeType.objects.values_list("name", flat=True))

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        buffer = io.StringIO()

        # ====== FULL ACCOUNT LIST + BULK UPLOAD COLUMNS ======
        headers = ["Member Name", "Member Number"]

        # Savings: Deposit only
        for st in saving_types:
            headers += [f"{st} Deposit"]

        # Fees: Payment only
        for ft in fee_types:
            headers += [f"{ft} Payment"]

        # write headers
        writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
        writer.writeheader()

        # write data
        for user in data:
            row = {
                "Member Name": user["member_name"],
                "Member Number": user["member_no"],
            }

            # initialize all to empty
            for st in saving_types:
                row[f"{st} Deposit"] = ""

            for ft in fee_types:
                row[f"{ft} Payment"] = ""

            # write row
            writer.writerow(row)

        file_name = f"bulk-upload-template-{date.today().strftime('%Y-%m-%d')}.csv"
        cloudinary_path = f"sproutsacco/bulk-upload-templates/{file_name}"

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
    Bulk upload accounts: Savings Deposits and Fee Payments
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
            saving_types = list(SavingType.objects.all().values_list("name", flat=True))
            fee_types = list(FeeType.objects.all().values_list("name", flat=True))
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
                public_id=f"sproutsacco/bulk-uploads/{prefix}_{file.name}",
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

        payment_method_name = request.data.get("payment_method")
        if not payment_method_name or not str(payment_method_name).strip():
            pay_method = get_default_payment_method()
            payment_method_name = pay_method.name if pay_method else None

        for index, row in enumerate(reader, 1):
            member_no = row.get("Member Number")
            if not member_no:
                continue

            # --- SAVINGS DEPOSITS ---
            for st in saving_types:
                amount_key = f"{st} Deposit"

                if row.get(amount_key):
                    try:
                        amount = Decimal(row[amount_key])
                        if amount > 0:
                            # Dynamically look up the savings account
                            savings_acc = SavingsAccount.objects.filter(
                                member__member_no=member_no,
                                account_type__name=st
                            ).first()

                            if not savings_acc:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Savings {st}",
                                        "error": f"Savings account of type '{st}' not found for member '{member_no}'",
                                    }
                                )
                                continue

                            data = {
                                "savings_account": savings_acc.account_number,
                                "amount": amount,
                                "payment_method": payment_method_name,
                                "deposit_type": "Individual Deposit",
                                "transaction_status": "Completed",
                            }
                            serializer = SavingsDepositSerializer(data=data)
                            if serializer.is_valid():
                                with transaction.atomic():
                                    deposit = serializer.save(deposited_by=admin)
                                    process_savings_deposit_accounting(deposit)
                                success_count += 1
                                # Email
                                if deposit.balance_updated and deposit.posted_to_gl:
                                    if deposit.savings_account.member.email:
                                        try:
                                            send_deposit_made_email(
                                                deposit.savings_account.member, deposit
                                            )
                                        except Exception as e:
                                            logger.warning(f"Email failed: {deposit.reference}")
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

            # --- FEE PAYMENTS ---
            for ft in fee_types:
                amount_key = f"{ft} Payment"

                if row.get(amount_key):
                    try:
                        amount = Decimal(row[amount_key])
                        if amount > 0:
                            # Dynamically look up the fee account
                            fee_acc = FeeAccount.objects.filter(
                                member__member_no=member_no,
                                fee_type__name=ft
                            ).first()

                            if not fee_acc:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Fee {ft}",
                                        "error": f"Fee account of type '{ft}' not found for member '{member_no}'",
                                    }
                                )
                                continue

                            data = {
                                "fee_account": fee_acc.account_number,
                                "amount": amount,
                                "payment_method": payment_method_name,
                                "transaction_status": "Completed",
                            }
                            serializer = FeePaymentSerializer(data=data)
                            if serializer.is_valid():
                                with transaction.atomic():
                                    instance = serializer.save(paid_by=admin)
                                    process_fee_payment_accounting(instance)
                                success_count += 1
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "type": f"Fee {ft}",
                                        "error": serializer.errors,
                                    }
                                )
                    except Exception as e:
                        error_count += 1
                        errors.append(
                            {"row": index, "type": f"Fee {ft}", "error": str(e)}
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


# =========================================================
# FINANCIAL SUMMARY
# =========================================================


class MemberYearlySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, member_no, *args, **kwargs):
        user = get_object_or_404(User, member_no=member_no)
        try:
            year = int(request.query_params.get("year", datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid year format"}, status=status.HTTP_400_BAD_REQUEST
            )

        summary = {
            "year": year,
            "member_no": user.member_no,
            "member_name": user.get_full_name(),
            "savings": self.get_savings_summary(user, year),
            "fees": self.get_fee_summary(user, year),
            "loans": self.get_loan_summary(user, year),
        }
        return Response(summary)

    def get_savings_summary(self, user, year):
        accounts = SavingsAccount.objects.filter(member=user).select_related(
            "account_type"
        )
        summary = []

        for acc in accounts:
            monthly_data = []

            # Yearly Totals
            total_yearly_deposits = SavingsDeposit.objects.filter(
                savings_account=acc,
                transaction_date__year=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # Balance Brought Forward
            bf_deposits = SavingsDeposit.objects.filter(
                savings_account=acc,
                transaction_date__year__lt=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            running_balance = bf_deposits

            for month in range(1, 13):
                # Monthly Aggregates
                month_deposits_qs = SavingsDeposit.objects.filter(
                    savings_account=acc,
                    transaction_date__year=year,
                    transaction_date__month=month,
                    transaction_status="Completed",
                    balance_updated=True,
                )

                month_deposits_total = month_deposits_qs.aggregate(total=Sum("amount"))[
                    "total"
                ] or Decimal("0")

                # Fetch Transactions
                transactions = []
                for deposit in month_deposits_qs.order_by("transaction_date"):
                    transactions.append(
                        {
                            "date": deposit.transaction_date,
                            "type": "Savings Deposit",
                            "amount": deposit.amount,
                            "reference": deposit.reference,
                            "method": (
                                deposit.payment_method.name
                                if deposit.payment_method
                                else "N/A"
                            ),
                        }
                    )

                opening = running_balance
                running_balance += month_deposits_total

                monthly_data.append(
                    {
                        "month": calendar.month_name[month],
                        "month_num": month,
                        "opening_balance": opening,
                        "deposits": month_deposits_total,
                        "withdrawals": Decimal("0.00"),
                        "closing_balance": running_balance,
                        "transactions": transactions,
                    }
                )

            summary.append(
                {
                    "account_number": acc.account_number,
                    "type": acc.account_type.name,
                    "currency": "KES",
                    "totals": {"total_deposits": total_yearly_deposits},
                    "monthly_summary": monthly_data,
                }
            )
        return summary

    def get_fee_summary(self, user, year):
        accounts = FeeAccount.objects.filter(member=user).select_related("fee_type")
        summary = []

        for acc in accounts:
            monthly_data = []
            target_amount = acc.fee_type.amount

            # Yearly Totals
            total_yearly_paid = FeePayment.objects.filter(
                fee_account=acc,
                transaction_date__year=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # Total paid before this year
            bf_paid = FeePayment.objects.filter(
                fee_account=acc,
                transaction_date__year__lt=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # Current outstanding at start of year
            running_outstanding = target_amount - bf_paid

            for month in range(1, 13):
                # Monthly Aggregates
                month_payments_qs = FeePayment.objects.filter(
                    fee_account=acc,
                    transaction_date__year=year,
                    transaction_date__month=month,
                    transaction_status="Completed",
                    balance_updated=True,
                )

                month_payments_total = month_payments_qs.aggregate(total=Sum("amount"))[
                    "total"
                ] or Decimal("0")

                # Fetch Transactions
                transactions = []
                for payment in month_payments_qs.order_by("transaction_date"):
                    transactions.append(
                        {
                            "date": payment.transaction_date,
                            "type": "Fee Payment",
                            "amount": payment.amount,
                            "reference": payment.reference,
                            "method": (
                                payment.payment_method.name
                                if payment.payment_method
                                else "N/A"
                            ),
                        }
                    )

                opening = running_outstanding
                running_outstanding -= month_payments_total
                closing = running_outstanding

                monthly_data.append(
                    {
                        "month": calendar.month_name[month],
                        "month_num": month,
                        "opening_balance": opening,
                        "payments": month_payments_total,
                        "closing_balance": closing,
                        "transactions": transactions,
                    }
                )

            summary.append(
                {
                    "account_number": acc.account_number,
                    "fee_type": acc.fee_type.name,
                    "currency": "KES",
                    "totals": {
                        "target_amount": target_amount,
                        "total_paid_yearly": total_yearly_paid,
                        "total_paid_to_date": target_amount - running_outstanding,
                        "balance_remaining": running_outstanding,
                    },
                    "monthly_summary": monthly_data,
                }
            )
        return summary


    def get_loan_summary(self, user, year):
        accounts = LoanAccount.objects.filter(member=user).select_related("product")
        summary = []

        for acc in accounts:
            monthly_data = []

            # Yearly Totals
            total_yearly_disbursed = LoanDisbursement.objects.filter(
                loan_account=acc,
                transaction_date__year=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            total_yearly_repaid = LoanPayment.objects.filter(
                loan_account=acc,
                transaction_date__year=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # Loans Cash Flow Logic:
            # Positive Balance = OUTSTANDING DEBT

            bf_disbursed = LoanDisbursement.objects.filter(
                loan_account=acc,
                transaction_date__year__lt=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            bf_paid = LoanPayment.objects.filter(
                loan_account=acc,
                transaction_date__year__lt=year,
                transaction_status="Completed",
                balance_updated=True,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            # B/F Debt = Disbursed - Paid
            running_balance = bf_disbursed - bf_paid

            for month in range(1, 13):
                # Monthly Aggregates
                month_disbursed_qs = LoanDisbursement.objects.filter(
                    loan_account=acc,
                    transaction_date__year=year,
                    transaction_date__month=month,
                    transaction_status="Completed",
                    balance_updated=True,
                )
                month_disbursed_total = month_disbursed_qs.aggregate(
                    total=Sum("amount")
                )["total"] or Decimal("0")

                month_paid_qs = LoanPayment.objects.filter(
                    loan_account=acc,
                    transaction_date__year=year,
                    transaction_date__month=month,
                    transaction_status="Completed",
                    balance_updated=True,
                )
                month_paid_total = month_paid_qs.aggregate(total=Sum("amount"))[
                    "total"
                ] or Decimal("0")

                # Fetch Transactions & Combine
                transactions = []
                for dis in month_disbursed_qs:
                    transactions.append(
                        {
                            "date": dis.transaction_date,
                            "type": "Loan Disbursement",
                            "amount": dis.amount,
                            "reference": dis.reference,
                        }
                    )

                for rep in month_paid_qs:
                    transactions.append(
                        {
                            "date": rep.transaction_date,
                            "type": "Loan Repayment",
                            "amount": rep.amount,
                            "reference": rep.reference,
                            "method": (
                                rep.payment_method.name if rep.payment_method else "N/A"
                            ),
                        }
                    )

                # Sort by date
                transactions.sort(key=lambda x: x["date"])

                opening = running_balance
                # Debt increases with disbursement, decreases with payment
                running_balance = (
                    running_balance + month_disbursed_total - month_paid_total
                )

                monthly_data.append(
                    {
                        "month": calendar.month_name[month],
                        "month_num": month,
                        "opening_balance": opening,
                        "disbursed": month_disbursed_total,
                        "paid": month_paid_total,
                        "closing_balance": running_balance,
                        "transactions": transactions,
                    }
                )

            summary.append(
                {
                    "account_number": acc.account_number,
                    "product": acc.product.name,
                    "initial_principal": acc.principal,
                    "totals": {
                        "total_disbursed": total_yearly_disbursed,
                        "total_repaid": total_yearly_repaid,
                    },
                    "monthly_summary": monthly_data,
                }
            )

        return summary


class MemberYearlySummaryPDFView(MemberYearlySummaryView):
    def get(self, request, member_no, *args, **kwargs):
        # reuse the logic from parent view
        user = get_object_or_404(User, member_no=member_no)
        try:
            year = int(request.query_params.get("year", datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid year format"}, status=status.HTTP_400_BAD_REQUEST
            )

        context = {
            "year": year,
            "member_no": user.member_no,
            "member_name": user.get_full_name(),
            "savings": self.get_savings_summary(user, year),
            "fees": self.get_fee_summary(user, year),
            "loans": self.get_loan_summary(user, year),
        }

        html_string = render_to_string("member_yearly_summary.html", context)

        # Ensure playwright is handled correctly
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_string)
            pdf_data = page.pdf(
                format="A4",
                margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                print_background=True,
            )
            browser.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Yearly_Summary_{member_no}_{year}.pdf"'
        )
        return response


class SaccoYearlySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get_summary_data(self, year):
        monthly_summary = []

        # Initialize Yearly Totals
        yearly_totals = {
            "savings_deposits": Decimal("0"),
            "fee_payments": Decimal("0"),
            "loan_disbursements": Decimal("0"),
            "loan_repayments": Decimal("0"),
            "total_new_members": 0,
            "counts": {
                "savings_deposits": 0,
                "fee_payments": 0,
                "loan_disbursements": 0,
                "loan_repayments": 0,
            },
        }

        for month in range(1, 13):
            month_data = {
                "month": calendar.month_name[month],
                "month_num": month,
                "new_members": 0,
                "counts": {
                    "savings_deposits": 0,
                    "fee_payments": 0,
                    "loan_disbursements": 0,
                    "loan_repayments": 0,
                },
                "savings": {"total": Decimal("0"), "breakdown": {}},
                "fees": {"total": Decimal("0"), "breakdown": {}},
                "loans": {
                    "disbursed": {"total": Decimal("0"), "breakdown": {}},
                    "repaid": {"total": Decimal("0"), "breakdown": {}},
                },
            }

            # ---- NEW MEMBERS ----
            new_members_count = User.objects.filter(
                created_at__year=year, created_at__month=month, is_member=True
            ).count()
            month_data["new_members"] = new_members_count
            yearly_totals["total_new_members"] += new_members_count

            # ---- SAVINGS ----
            savings_qs = SavingsDeposit.objects.filter(
                created_at__year=year,
                created_at__month=month,
                transaction_status="Completed",
            )
            # Group by Account Type
            savings_breakdown = savings_qs.values(
                "savings_account__account_type__name"
            ).annotate(total=Sum("amount"), count=Count("id"))
            for item in savings_breakdown:
                amt = item["total"] or Decimal("0")
                count = item["count"]
                name = item["savings_account__account_type__name"]

                month_data["savings"]["breakdown"][name] = amt
                month_data["savings"]["total"] += amt
                month_data["counts"]["savings_deposits"] += count

                yearly_totals["savings_deposits"] += amt
                yearly_totals["counts"]["savings_deposits"] += count

            # ---- FEE PAYMENTS ----
            fee_pay_qs = FeePayment.objects.filter(
                created_at__year=year,
                created_at__month=month,
                transaction_status="Completed",
            )
            fee_pay_breakdown = fee_pay_qs.values(
                "fee_account__fee_type__name"
            ).annotate(total=Sum("amount"), count=Count("id"))
            for item in fee_pay_breakdown:
                amt = item["total"] or Decimal("0")
                count = item["count"]
                name = item["fee_account__fee_type__name"]

                month_data["fees"]["breakdown"][name] = amt
                month_data["fees"]["total"] += amt
                month_data["counts"]["fee_payments"] += count

                yearly_totals["fee_payments"] += amt
                yearly_totals["counts"]["fee_payments"] += count

            # ---- LOAN DISBURSEMENTS ----
            l_dis_qs = LoanDisbursement.objects.filter(
                created_at__year=year,
                created_at__month=month,
                transaction_status="Completed",
            )
            l_dis_breakdown = l_dis_qs.values("loan_account__product__name").annotate(
                total=Sum("amount"), count=Count("id")
            )
            for item in l_dis_breakdown:
                amt = item["total"] or Decimal("0")
                count = item["count"]
                name = item["loan_account__product__name"]

                month_data["loans"]["disbursed"]["breakdown"][name] = amt
                month_data["loans"]["disbursed"]["total"] += amt
                month_data["counts"]["loan_disbursements"] += count

                yearly_totals["loan_disbursements"] += amt
                yearly_totals["counts"]["loan_disbursements"] += count

            # ---- LOAN REPAYMENTS ----
            l_rep_qs = LoanPayment.objects.filter(
                payment_date__year=year,
                payment_date__month=month,
                transaction_status="Completed",
            )
            l_rep_breakdown = l_rep_qs.values("loan_account__product__name").annotate(
                total=Sum("amount"), count=Count("id")
            )
            for item in l_rep_breakdown:
                amt = item["total"] or Decimal("0")
                count = item["count"]
                name = item["loan_account__product__name"]

                month_data["loans"]["repaid"]["breakdown"][name] = amt
                month_data["loans"]["repaid"]["total"] += amt
                month_data["counts"]["loan_repayments"] += count

                yearly_totals["loan_repayments"] += amt
                yearly_totals["counts"]["loan_repayments"] += count

            monthly_summary.append(month_data)

        return {
            "year": year,
            "generated_at": datetime.now(),
            "totals": yearly_totals,
            "monthly_summary": monthly_summary,
        }

    def get(self, request, *args, **kwargs):
        try:
            year = int(request.query_params.get("year", datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid year format"}, status=status.HTTP_400_BAD_REQUEST
            )

        data = self.get_summary_data(year)
        return Response(data)


class SaccoYearlySummaryPDFView(SaccoYearlySummaryView):
    def get(self, request, *args, **kwargs):
        try:
            year = int(request.query_params.get("year", datetime.now().year))
        except ValueError:
            return Response(
                {"error": "Invalid year format"}, status=status.HTTP_400_BAD_REQUEST
            )

        context = self.get_summary_data(year)

        html_string = render_to_string("sacco_yearly_summary.html", context)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html_string)
            # Use landscape for SACCO summary as it has many columns
            pdf_data = page.pdf(
                format="A4",
                landscape=True,
                margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                print_background=True,
            )
            browser.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="SACCO_Yearly_Summary_{year}.pdf"'
        )
        return response


class FinancialReportsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Handles requests for different report types.
        /reports/?type=<type>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&as_of=YYYY-MM-DD
        If type is not provided, returns all reports.
        """
        report_type = request.query_params.get("type")

        try:
            start_date_str = request.query_params.get("start_date")
            end_date_str = request.query_params.get("end_date")
            as_of_str = request.query_params.get("as_of")

            start_date = (
                datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if start_date_str
                else None
            )
            end_date = (
                datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if end_date_str
                else timezone.now().date()
            )
            as_of_date = (
                datetime.strptime(as_of_str, "%Y-%m-%d").date()
                if as_of_str
                else timezone.now().date()
            )

        except ValueError:
            return Response(
                {"error": "Invalid date format (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {}

        if report_type:
            start_time = timezone.now()
            if report_type == "debtors":
                data = get_debtors_report()
                logger.info(
                    f"Generated debtors report in {timezone.now() - start_time}"
                )

            elif report_type == "balance-sheet":
                data = get_balance_sheet(as_of_date=as_of_date)
                logger.info(f"Generated balance sheet in {timezone.now() - start_time}")

            elif report_type == "pnl":
                if not start_date:
                    # Default to current month start if not provided
                    today = timezone.now().date()
                    start_date = today.replace(day=1)

                data = get_pnl(start_date=start_date, end_date=end_date)
                logger.info(f"Generated P&L in {timezone.now() - start_time}")

            elif report_type == "cash-book":
                data = get_cash_book(start_date=start_date, end_date=end_date)
                logger.info(f"Generated cash book in {timezone.now() - start_time}")

            else:
                return Response(
                    {"error": "Invalid report type"}, status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Fetch All Reports
            total_start_time = timezone.now()
            if not start_date:
                today = timezone.now().date()
                start_date = today.replace(day=1)

            data = {
                "debtors": get_debtors_report(),
                "balance_sheet": get_balance_sheet(as_of_date=as_of_date),
                "pnl": get_pnl(start_date=start_date, end_date=end_date),
                "cash_book": get_cash_book(start_date=start_date, end_date=end_date),
            }
            logger.info(
                f"Generated all financial reports in {timezone.now() - total_start_time}"
            )

        return Response(data)


class UniversalTransactionTemplateView(APIView):
    """
    Generates a unified CSV template for:
    - Savings Deposits (All active accounts)
    - Fee Payments (Accounts with outstanding balances)
    - Loan Disbursements (Approved but not disbursed loans)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="universal_bulk_transactions_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Member Name",
                "Account Number",
                "Transaction Type",
                "Amount",
                "Payment Method",
            ]
        )

        # 1. Savings Deposits
        savings = SavingsAccount.objects.filter(is_active=True).select_related(
            "member", "account_type"
        )
        for acc in savings:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.account_number,
                    "Savings Deposit",
                    "",
                    "Cash",
                ]
            )

        # 2. Fee Payments
        fees = FeeAccount.objects.filter(outstanding_balance__gt=0).select_related(
            "member", "fee_type"
        )
        for acc in fees:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.account_number,
                    "Fee Payment",
                    "",
                    "Cash",
                ]
            )

        # 3. Loan Disbursements
        loans = LoanAccount.objects.filter(
            application__status="Approved"
        ).select_related("member", "product")
        for acc in loans:
            writer.writerow(
                [
                    acc.member.get_full_name(),
                    acc.account_number,
                    "Loan Disbursement",
                    "",
                    "Cash",
                ]
            )

        return response


class UniversalBulkTransactionUploadView(generics.CreateAPIView):
    """
    Unified bulk upload endpoint for Savings, Fees, and Loan Disbursements.
    Routes rows to their respective services based on "Transaction Type".
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BulkUploadSerializer

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
        prefix = f"UNI-BULK-{today.strftime('%Y%m%d')}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Universal Bulk Transaction",
            reference_prefix=prefix,
            file_name=file.name,
        )

        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_universal/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")

        success_count = 0
        error_count = 0
        errors = []

        payment_method_name = request.data.get("payment_method")
        if not payment_method_name or not str(payment_method_name).strip():
            pay_method = get_default_payment_method()
            payment_method_name = pay_method.name if pay_method else None

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    t_type = row.get("Transaction Type")
                    acc_num = row.get("Account Number")
                    amount_str = row.get("Amount")
                    payment_method = payment_method_name

                    if not amount_str or Decimal(amount_str) <= 0:
                        continue

                    if t_type == "Savings Deposit":
                        data = {
                            "savings_account": acc_num,
                            "amount": amount_str,
                            "payment_method": payment_method,
                            "transaction_status": "Completed",
                        }
                        serializer = SavingsDepositSerializer(data=data)
                        if serializer.is_valid():
                            deposit = serializer.save(deposited_by=admin)
                            process_savings_deposit_accounting(deposit)
                            if deposit.balance_updated and deposit.posted_to_gl:
                                if deposit.savings_account.member.email:
                                    send_deposit_made_email(
                                        deposit.savings_account.member, deposit
                                    )
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "type": t_type,
                                    "account": acc_num,
                                    "errors": serializer.errors,
                                }
                            )

                    elif t_type == "Fee Payment":
                        data = {
                            "fee_account": acc_num,
                            "amount": amount_str,
                            "payment_method": payment_method,
                            "transaction_status": "Completed",
                        }
                        serializer = FeePaymentSerializer(data=data)
                        if serializer.is_valid():
                            instance = serializer.save(paid_by=admin)
                            process_fee_payment_accounting(instance)
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "type": t_type,
                                    "account": acc_num,
                                    "errors": serializer.errors,
                                }
                            )

                    elif t_type == "Loan Disbursement":
                        data = {
                            "loan_account": acc_num,
                            "amount": amount_str,
                            "payment_method": payment_method,
                            "transaction_status": "Completed",
                            "disbursement_type": "Principal",
                        }
                        serializer = LoanDisbursementSerializer(data=data)
                        if serializer.is_valid():
                            disbursement = serializer.save(disbursed_by=admin)

                            # Trigger status update
                            loan_application = disbursement.loan_account.application
                            loan_application.status = "Disbursed"
                            loan_application.save()

                            process_loan_disbursement_accounting(disbursement)

                            if disbursement.loan_account.member.email:
                                send_disbursement_made_email(
                                    disbursement.loan_account.member, disbursement
                                )
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "type": t_type,
                                    "account": acc_num,
                                    "errors": serializer.errors,
                                }
                            )

                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "error": f"Unknown transaction type: {t_type}",
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
