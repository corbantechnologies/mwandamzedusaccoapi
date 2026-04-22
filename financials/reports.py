# financials/reports.py
import calendar
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone

from glaccounts.models import GLAccount
from journalentries.models import JournalEntry

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
CASH_ACCOUNT_CODES = ["10000", "11000"]

DR_NORMAL_CATEGORIES = {"ASSET", "EXPENSE"}
CR_NORMAL_CATEGORIES = {"LIABILITY", "EQUITY", "REVENUE"}


# ---------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------

def _net_balance(account, as_of_date=None, start_date=None, end_date=None):
    """
    Compute the net balance for a single GL account from journal entries.

    - If as_of_date is given: cumulative balance up to and including that date.
    - If start_date and end_date are given: net movement within the period.
    - Normal balance direction is applied so the returned value is always
      a positive number when the account has activity in its natural direction.
    """
    qs = JournalEntry.objects.filter(account=account, batch__posted=True)

    if as_of_date:
        qs = qs.filter(batch__posting_date__lte=as_of_date)
    elif start_date and end_date:
        qs = qs.filter(
            batch__posting_date__gte=start_date,
            batch__posting_date__lte=end_date,
        )

    agg = qs.aggregate(total_dr=Sum("debit"), total_cr=Sum("credit"))
    total_dr = agg["total_dr"] or Decimal("0")
    total_cr = agg["total_cr"] or Decimal("0")

    if account.category in DR_NORMAL_CATEGORIES:
        return total_dr - total_cr
    else:
        return total_cr - total_dr


def _account_row(account, balance):
    """Build a standard serializable account row."""
    return {
        "id": str(account.id),
        "reference": account.reference,
        "code": account.code,
        "name": account.name,
        "category": account.category,
        "balance": balance,
    }


# ---------------------------------------------------------
# 1. Trial Balance
# ---------------------------------------------------------

def get_trial_balance(as_of_date=None):
    """
    Returns the trial balance as of a given date (defaults to today).

    The trial balance lists every active GL account with its total debits
    and credits computed from posted journal entries. The grand total of
    all debits must equal the grand total of all credits.
    """
    if not as_of_date:
        as_of_date = timezone.now().date()

    accounts = GLAccount.objects.filter(is_active=True).order_by("code")

    rows = []
    grand_dr = Decimal("0")
    grand_cr = Decimal("0")

    for account in accounts:
        qs = JournalEntry.objects.filter(
            account=account,
            batch__posted=True,
            batch__posting_date__lte=as_of_date,
        )
        agg = qs.aggregate(total_dr=Sum("debit"), total_cr=Sum("credit"))
        total_dr = agg["total_dr"] or Decimal("0")
        total_cr = agg["total_cr"] or Decimal("0")

        if total_dr == 0 and total_cr == 0:
            continue  # Skip dormant accounts

        rows.append({
            "code": account.code,
            "name": account.name,
            "category": account.category,
            "total_debit": total_dr,
            "total_credit": total_cr,
        })

        grand_dr += total_dr
        grand_cr += total_cr

    return {
        "as_of": as_of_date,
        "generated_at": timezone.now(),
        "accounts": rows,
        "totals": {
            "total_debit": grand_dr,
            "total_credit": grand_cr,
            "is_balanced": grand_dr == grand_cr,
        },
    }


# ---------------------------------------------------------
# 2. Balance Sheet
# ---------------------------------------------------------

def get_balance_sheet(as_of_date=None):
    """
    Returns the Balance Sheet as of a given date (defaults to today).

    Structure:
        ASSETS
            - Each Asset account with its net balance
        LIABILITIES
            - Each Liability account
        EQUITY
            - Each Equity account
            - Current Period Net Income (Revenue - Expenses, auto-calculated)
        Verification: Total Assets == Total Liabilities + Total Equity
    """
    if not as_of_date:
        as_of_date = timezone.now().date()

    accounts = GLAccount.objects.filter(is_active=True).order_by("code")

    assets = []
    liabilities = []
    equity_accounts = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for account in accounts:
        balance = _net_balance(account, as_of_date=as_of_date)

        if account.category == "ASSET":
            assets.append(_account_row(account, balance))
            total_assets += balance

        elif account.category == "LIABILITY":
            liabilities.append(_account_row(account, balance))
            total_liabilities += balance

        elif account.category == "EQUITY":
            equity_accounts.append(_account_row(account, balance))
            total_equity += balance

        elif account.category == "REVENUE":
            total_revenue += balance

        elif account.category == "EXPENSE":
            total_expenses += balance

    # Net income appears as a component of equity on the balance sheet
    current_period_net_income = total_revenue - total_expenses
    total_equity_including_income = total_equity + current_period_net_income

    return {
        "as_of": as_of_date,
        "generated_at": timezone.now(),
        "assets": {
            "accounts": assets,
            "total": total_assets,
        },
        "liabilities": {
            "accounts": liabilities,
            "total": total_liabilities,
        },
        "equity": {
            "accounts": equity_accounts,
            "current_period_net_income": current_period_net_income,
            "total": total_equity_including_income,
        },
        "totals": {
            "total_assets": total_assets,
            "total_liabilities_and_equity": total_liabilities + total_equity_including_income,
            "is_balanced": total_assets == (total_liabilities + total_equity_including_income),
        },
    }


# ---------------------------------------------------------
# 3. Profit & Loss Statement
# ---------------------------------------------------------

def get_pnl_statement(start_date=None, end_date=None):
    """
    Returns the Profit & Loss statement for a given period.

    Defaults to the first and last day of the current month when no
    dates are provided. Revenue accounts represent income; Expense
    accounts represent costs. Net Income = Total Revenue - Total Expenses.
    """
    today = timezone.now().date()
    if not start_date:
        start_date = today.replace(day=1)
    if not end_date:
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day)

    accounts = GLAccount.objects.filter(
        is_active=True, category__in=["REVENUE", "EXPENSE"]
    ).order_by("code")

    revenue_accounts = []
    expense_accounts = []
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for account in accounts:
        balance = _net_balance(account, start_date=start_date, end_date=end_date)

        if account.category == "REVENUE":
            revenue_accounts.append(_account_row(account, balance))
            total_revenue += balance
        elif account.category == "EXPENSE":
            expense_accounts.append(_account_row(account, balance))
            total_expenses += balance

    net_income = total_revenue - total_expenses

    return {
        "period": {"start": start_date, "end": end_date},
        "generated_at": timezone.now(),
        "revenue": {
            "accounts": revenue_accounts,
            "total": total_revenue,
        },
        "expenses": {
            "accounts": expense_accounts,
            "total": total_expenses,
        },
        "net_income": net_income,
    }


# ---------------------------------------------------------
# 4. Cash Balance
# ---------------------------------------------------------

def get_cash_balances(as_of_date=None):
    """
    Returns the balances for the designated cash and bank GL accounts.

    Cash accounts are identified by their GL code:
        10000 → Cash at Hand
        11000 → Cash at Bank

    Users must configure their Chart of Accounts to use these specific
    codes during initial setup.
    """
    if not as_of_date:
        as_of_date = timezone.now().date()

    cash_accounts = GLAccount.objects.filter(
        code__in=CASH_ACCOUNT_CODES, is_active=True
    ).order_by("code")

    accounts = []
    total_cash = Decimal("0")

    for account in cash_accounts:
        balance = _net_balance(account, as_of_date=as_of_date)
        accounts.append(_account_row(account, balance))
        total_cash += balance

    return {
        "as_of": as_of_date,
        "generated_at": timezone.now(),
        "accounts": accounts,
        "total_cash": total_cash,
        "note": "Cash accounts are identified by GL codes 10000 (Cash at Hand) and 11000 (Cash at Bank).",
    }
