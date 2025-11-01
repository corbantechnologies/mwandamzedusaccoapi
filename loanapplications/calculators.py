from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, List


def flat_rate_projection(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date,
    repayment_frequency: str = "monthly",
) -> Dict:
    """Generate full flat-rate repayment schedule."""
    DELTA = {
        "daily": relativedelta(days=1),
        "weekly": relativedelta(weeks=1),
        "biweekly": relativedelta(weeks=2),
        "monthly": relativedelta(months=1),
        "quarterly": relativedelta(months=3),
        "annually": relativedelta(years=1),
    }
    MONTHS_IN_PERIOD = {
        "daily": Decimal("1") / 30,
        "weekly": Decimal("1") / 4,
        "biweekly": Decimal("0.5"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("3"),
        "annually": Decimal("12"),
    }

    if repayment_frequency not in DELTA:
        raise ValueError(f"Unsupported frequency: {repayment_frequency}")

    payment_delta = DELTA[repayment_frequency]
    months_per_period = MONTHS_IN_PERIOD[repayment_frequency]

    rate = annual_rate / Decimal("100")
    total_interest = (principal * rate * Decimal(term_months) / Decimal("12")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    total_repayment = principal + total_interest
    total_periods = int(term_months / months_per_period)

    payment_per_period = (total_repayment / Decimal(total_periods)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    interest_per_period = (total_interest / Decimal(total_periods)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    principal_per_period = payment_per_period - interest_per_period

    balance = principal
    schedule: List[dict] = []
    cur_date = start_date

    for _ in range(total_periods):
        due = cur_date
        if balance <= principal_per_period:
            principal_due = balance
            interest_due = interest_per_period
            total_due = principal_due + interest_due
        else:
            principal_due = principal_per_period
            interest_due = interest_per_period
            total_due = payment_per_period

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)

        schedule.append(
            {
                "due_date": due.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest_due),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )
        cur_date += payment_delta

    monthly_payment = payment_per_period / months_per_period

    return {
        "term_months": term_months,
        "monthly_payment": float(monthly_payment.quantize(Decimal("0.01"))),
        "total_interest": float(total_interest),
        "total_repayment": float(total_repayment),
        "schedule": schedule,
    }
