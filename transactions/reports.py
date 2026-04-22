from decimal import Decimal
from django.db.models import Sum, Q, Max
from django.utils import timezone
from datetime import datetime, date, time
from collections import defaultdict

from loanaccounts.models import LoanAccount
from savings.models import SavingsAccount
from ventureaccounts.models import VentureAccount
from savingsdeposits.models import SavingsDeposit
from venturedeposits.models import VentureDeposit
from venturepayments.models import VenturePayment
from loandisbursements.models import LoanDisbursement
from loanpayments.models import LoanPayment


def make_day_range(date_obj):
    """
    Helper to create start and end datetime for a given date.
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    start = timezone.make_aware(datetime.combine(date_obj, time.min))
    end = timezone.make_aware(datetime.combine(date_obj, time.max))
    return start, end


def get_debtors_report():
    """
    Returns a list of members with outstanding loans.
    """
    debtors = (
        LoanAccount.objects.filter(outstanding_balance__gt=0)
        .annotate(last_payment_date=Max("loan_payments__payment_date"))
        .select_related("member", "product")
    )

    report = []
    total_outstanding = Decimal("0")
    total_interest = Decimal("0")
    total_processing_fee = Decimal("0")

    for loan in debtors:
        report.append(
            {
                "member_name": loan.member.get_full_name(),
                "member_no": loan.member.member_no,
                "loan_product": loan.product.name,
                "account_number": loan.account_number,
                "principal": loan.principal,
                "total_interest": loan.total_interest_accrued,
                "processing_fee": loan.processing_fee,
                "outstanding_balance": loan.outstanding_balance,
                "status": loan.status,
                "last_payment_date": loan.last_payment_date,
            }
        )
        total_outstanding += loan.outstanding_balance
        total_interest += loan.total_interest_accrued
        total_processing_fee += loan.processing_fee

    return {
        "generated_at": timezone.now(),
        "total_outstanding": total_outstanding,
        "total_interest_summary": total_interest,
        "total_processing_fee_summary": total_processing_fee,
        "debtors": report,
    }


def get_balance_sheet(as_of_date=None):
    """
    Returns Assets, Liabilities, and Equity.
    """
    if not as_of_date:
        as_of_date = timezone.now().date()

    end_dt = timezone.make_aware(datetime.combine(as_of_date, time.max))

    # --- ASSETS ---
    # 1. Loans Receivable
    total_loans_receivable = LoanAccount.objects.aggregate(
        total=Sum("outstanding_balance")
    )["total"] or Decimal("0")

    # 2. Cash at Hand / Bank
    # Inflows
    total_savings_in = SavingsDeposit.objects.filter(
        transaction_status="Completed", created_at__lte=end_dt
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    total_venture_in = VentureDeposit.objects.filter(created_at__lte=end_dt).aggregate(
        t=Sum("amount")
    )["t"] or Decimal("0")

    total_loan_repayments_in = LoanPayment.objects.filter(
        transaction_status="Completed", payment_date__lte=end_dt
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # Outflows
    total_loan_disbursements_out = LoanDisbursement.objects.filter(
        transaction_status="Completed", created_at__lte=end_dt
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    total_venture_payments_out = VenturePayment.objects.filter(
        transaction_status="Completed", payment_date__lte=end_dt
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    total_cash_in = total_savings_in + total_venture_in + total_loan_repayments_in
    total_cash_out = total_loan_disbursements_out + total_venture_payments_out

    cash_asset = total_cash_in - total_cash_out

    # Total Assets
    total_assets = cash_asset + total_loans_receivable

    # --- LIABILITIES ---
    # 1. Member Savings
    total_savings_liability = total_savings_in

    # 2. Venture Funds (Net held)
    net_venture_liability = total_venture_in - total_venture_payments_out

    total_liabilities = total_savings_liability + net_venture_liability

    # --- EQUITY ---
    equity = total_assets - total_liabilities

    return {
        "as_of": as_of_date,
        "assets": {
            "cash_equivalents": cash_asset,
            "loans_receivable": total_loans_receivable,
            "total_assets": total_assets,
        },
        "liabilities": {
            "member_savings": total_savings_liability,
            "venture_funds": net_venture_liability,
            "total_liabilities": total_liabilities,
        },
        "equity": equity,
    }


def get_pnl(start_date, end_date):
    """
    Profit and Loss Statement.
    """
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max))

    # INCOME (Cash Basis Proxy)
    income_loans = LoanPayment.objects.filter(
        transaction_status="Completed",
        payment_date__gte=start_dt,
        payment_date__lte=end_dt,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # EXPENSES
    expenses_ventures = VenturePayment.objects.filter(
        transaction_status="Completed",
        payment_date__gte=start_date,  # Use date
        payment_date__lte=end_date,  # Use date
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    net_income = income_loans - expenses_ventures

    return {
        "period": {"start": start_date, "end": end_date},
        "income": {"loan_repayments_gross": income_loans, "total_income": income_loans},
        "expenses": {
            "venture_payouts": expenses_ventures,
            "total_expenses": expenses_ventures,
        },
        "net_income": net_income,
    }


def get_cash_book(start_date=None, end_date=None):
    """
    Detailed list of all cash transactions.
    """
    if not start_date:
        today = timezone.now().date()
        start_date = today.replace(day=1)
    if not end_date:
        end_date = timezone.now().date()

    start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max))

    transactions = []

    # 1. Savings Deposits (+)
    savings = SavingsDeposit.objects.filter(
        transaction_status="Completed", created_at__gte=start_dt, created_at__lte=end_dt
    ).select_related("savings_account__member")

    for s in savings:
        transactions.append(
            {
                "date": s.created_at,
                "description": f"Savings Deposit - {s.savings_account.member.get_full_name()}",
                "reference": s.reference,
                "type": "Debit",
                "amount": s.amount,
                "category": "Savings",
            }
        )

    # 2. Venture Deposits (+)
    ventures_in = VentureDeposit.objects.filter(
        created_at__gte=start_dt, created_at__lte=end_dt
    ).select_related("venture_account__member")

    for v in ventures_in:
        transactions.append(
            {
                "date": v.created_at,
                "description": f"Venture Deposit - {v.venture_account.member.get_full_name()}",
                "reference": v.reference,
                "type": "Debit",
                "amount": v.amount,
                "category": "Venture Deposit",
            }
        )

    # 3. Loan Repayments (+)
    loans_in = LoanPayment.objects.filter(
        transaction_status="Completed",
        payment_date__gte=start_dt,
        payment_date__lte=end_dt,
    ).select_related("loan_account__member")

    for l in loans_in:
        # Normalize to datetime if it's a date (though payment_date is DateTimeField,
        # let's be safe or just use it as is if we know it's datetime)
        dt = l.payment_date
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = timezone.make_aware(datetime.combine(dt, time.min))

        transactions.append(
            {
                "date": dt,
                "description": f"Loan Repayment - {l.loan_account.member.get_full_name()}",
                "reference": l.reference or l.payment_code,
                "type": "Debit",
                "amount": l.amount,
                "category": "Loan Repayment",
            }
        )

    # 4. Loan Disbursements (-)
    loans_out = LoanDisbursement.objects.filter(
        transaction_status="Completed", created_at__gte=start_dt, created_at__lte=end_dt
    ).select_related("loan_account__member")

    for l in loans_out:
        transactions.append(
            {
                "date": l.created_at,
                "description": f"Loan Disbursement - {l.loan_account.member.get_full_name()}",
                "reference": l.reference,
                "type": "Credit",
                "amount": l.amount,
                "category": "Loan Disbursement",
            }
        )

    # 5. Venture Payments (-)
    ventures_out = VenturePayment.objects.filter(
        transaction_status="Completed",
        payment_date__gte=start_date,  # Use date
        payment_date__lte=end_date,  # Use date
    ).select_related("venture_account__member")

    for v in ventures_out:
        # Normalize DateField to datetime
        dt = v.payment_date
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = timezone.make_aware(datetime.combine(dt, time.min))

        transactions.append(
            {
                "date": dt,
                "description": f"Venture Payout - {v.venture_account.member.get_full_name()}",
                "reference": v.reference or v.receipt_number,
                "type": "Credit",
                "amount": v.amount,
                "category": "Venture Payout",
            }
        )

    start_dt_limit = start_dt  # effectively

    # Calculate Opening Balance
    opening_balance = Decimal("0")
    if start_dt:
        # Inflows
        open_sav = SavingsDeposit.objects.filter(
            transaction_status="Completed", created_at__lt=start_dt_limit
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        open_ven_in = VentureDeposit.objects.filter(
            created_at__lt=start_dt_limit
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        open_loan_in = LoanPayment.objects.filter(
            transaction_status="Completed", payment_date__lt=start_dt_limit
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        # Outflows
        open_loan_out = LoanDisbursement.objects.filter(
            transaction_status="Completed", created_at__lt=start_dt_limit
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        open_ven_out = VenturePayment.objects.filter(
            transaction_status="Completed", payment_date__lt=start_date  # Use date
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

        opening_balance = (open_sav + open_ven_in + open_loan_in) - (
            open_loan_out + open_ven_out
        )

    # Sort
    transactions.sort(key=lambda x: x["date"])  # date is datetime here

    running_balance = opening_balance
    final_transactions = []

    for t in transactions:
        amount = t["amount"]
        if t["type"] == "Debit":
            running_balance += amount
        else:
            running_balance -= amount

        t["running_balance"] = running_balance
        final_transactions.append(t)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "opening_balance": opening_balance,
        "closing_balance": running_balance,
        "transactions": final_transactions,
    }
