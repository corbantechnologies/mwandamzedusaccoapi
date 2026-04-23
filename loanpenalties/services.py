# loanpenalties/services.py
from datetime import datetime
from decimal import Decimal
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from .models import LoanPenalty
from mwandamzedusaccoapi.settings import LOAN_PENALTY_RATE


def apply_auto_targeted_penalty(loan_account, admin_user):
    """
    Identifies the oldest overdue installment and applies a penalty,
    ensuring total penalty instances never exceed the number of installments.
    """
    schedule = loan_account.projection_snapshot.get("schedule", [])
    total_installments = len(schedule)

    # 1. CEILING CHECK: Can we even add another penalty?
    # We count all penalties (Paid, Pending, etc.) because a penalty
    # represents a 'violation event' on a specific installment.
    existing_penalty_count = loan_account.penalties.exclude(status="Waived").count()

    if existing_penalty_count >= total_installments:
        raise ValidationError(
            f"Limit reached. This loan has {total_installments} installments, "
            f"and {existing_penalty_count} penalties have already been charged."
        )

    # 2. Skip Logic: Find the first installment that is NOT paid and NOT penalized
    penalized_codes = list(
        loan_account.penalties.filter(status__in=["Pending", "Paid"]).values_list(
            "installment_code", flat=True
        )
    )

    target_installment = None
    today = now().date()

    for row in schedule:
        code = row.get("installment_code")
        if not row.get("is_paid") and code not in penalized_codes:
            # Re-enable date check for production
            # due_date = datetime.strptime(row.get("due_date"), "%Y-%m-%d").date()
            # if today > due_date:
            target_installment = row
            break

    if not target_installment:
        raise ValidationError("No qualifying overdue installments found.")

    # 3. EXECUTION
    total_due = Decimal(str(target_installment.get("total_due", 0)))
    penalty_rate = Decimal(str(LOAN_PENALTY_RATE)) / Decimal("100")
    penalty_amount = round(total_due * penalty_rate, 2)

    return LoanPenalty.objects.create(
        loan_account=loan_account,
        installment_code=target_installment.get("installment_code"),
        amount=penalty_amount,
        status="Pending",
        charged_by=admin_user,
    )
