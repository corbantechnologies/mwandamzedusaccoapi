# loan_functions.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, List


def advance_date(current_date: date, frequency: str) -> date:
    """Helper to advance date by one period based on frequency."""
    if frequency == "monthly":
        return current_date + relativedelta(months=1)
    elif frequency == "weekly":
        return current_date + relativedelta(weeks=1)
    elif frequency == "biweekly":
        return current_date + relativedelta(weeks=2)
    elif frequency == "daily":
        return current_date + relativedelta(days=1)
    elif frequency == "quarterly":
        return current_date + relativedelta(months=3)
    elif frequency == "annually":
        return current_date + relativedelta(years=1)
    else:
        # Default to monthly if unknown, or raise error
        return current_date + relativedelta(months=1)


# ======================================================================
# 1. FLAT-RATE (Interest on original principal)
# ======================================================================
def flat_rate_fixed_payment(
    principal: Decimal,
    annual_rate: Decimal,
    payment_per_month: Decimal,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
    max_months: int = 360,
) -> Dict:
    """Fixed monthly payment → calculate term (Flat-rate)"""
    MONTHS_IN_PERIOD = {
        "daily": Decimal("1") / 30,
        "weekly": Decimal("1") / 4,
        "biweekly": Decimal("0.5"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("3"),
        "annually": Decimal("12"),
    }

    if repayment_frequency not in MONTHS_IN_PERIOD:
        # Default or raise
        pass

    months_per_period = MONTHS_IN_PERIOD.get(repayment_frequency, Decimal("1"))

    rate = annual_rate / Decimal("100")
    payment_this_period = (payment_per_month * months_per_period).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )

    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []

    # Start first payment 1 period after start_date
    cur_date = advance_date(start_date, repayment_frequency)

    months_elapsed = Decimal("0")

    interest_per_month = (principal * rate / Decimal("12")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    interest_this_period = interest_per_month * months_per_period

    while balance > Decimal("0.01") and months_elapsed < max_months:
        due = cur_date

        interest_due = min(interest_this_period, payment_this_period)
        principal_due = min(payment_this_period - interest_due, balance)
        total_due = interest_due + principal_due

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total_interest += interest_due

        schedule.append(
            {
                "due_date": due.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest_due),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )

        cur_date = advance_date(cur_date, repayment_frequency)
        months_elapsed += months_per_period

    term_months = int(months_elapsed.quantize(Decimal("1"), ROUND_HALF_UP))
    return {
        "term_months": term_months,
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }


def flat_rate_fixed_term(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
) -> Dict:
    """Fixed term → calculate monthly payment (Flat-rate)"""
    MONTHS_IN_PERIOD = {
        "daily": Decimal("1") / 30,
        "weekly": Decimal("1") / 4,
        "biweekly": Decimal("0.5"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("3"),
        "annually": Decimal("12"),
    }

    months_per_period = MONTHS_IN_PERIOD.get(repayment_frequency, Decimal("1"))

    rate = annual_rate / Decimal("100")
    total_interest = (principal * rate * Decimal(term_months) / Decimal("12")).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    total_repayment = principal + total_interest

    # total periods = term_months / months_per_period
    # e.g. 12 months, monthly=1 -> 12 periods. 12 months, weekly=0.25 -> 48 periods?
    # Logic in original was simple division.
    total_periods = int(Decimal(term_months) / months_per_period)
    if total_periods < 1:
        total_periods = 1

    payment_per_period = (total_repayment / Decimal(total_periods)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    interest_per_period = (total_interest / Decimal(total_periods)).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )
    principal_per_period = payment_per_period - interest_per_period

    balance = principal
    schedule: List[dict] = []

    # Start first payment 1 period after start_date
    cur_date = advance_date(start_date, repayment_frequency)

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
        cur_date = advance_date(cur_date, repayment_frequency)

    # Monthly payment is what user pays *per month*.
    # If frequency is weekly, payment_per_period is weekly amount.
    # We normalized output "monthly_payment" to be per month.
    output_monthly_payment = payment_per_period / months_per_period

    return {
        "term_months": term_months,
        "monthly_payment": float(output_monthly_payment),
        "total_interest": float(total_interest),
        "total_repayment": float(total_repayment),
        "schedule": schedule,
    }


# ======================================================================
# 2. REDUCING BALANCE (Diminishing Balance)
# ======================================================================
def reducing_fixed_term(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
) -> Dict:
    """
    REDUCING BALANCE: Member selects TERM (months) → Calculate MONTHLY PAYMENT
    Uses PMT formula.
    """
    if term_months <= 0:
        raise ValueError("Term months must be > 0")

    # Adjust N for frequency
    # "term_months" is passed. If frequency is weekly, N periods = term_months * 4.3?
    # Usually "term" is in months.
    # Formula uses N as number of PAYMENTS.

    MONTHS_IN_PERIOD = {
        "daily": Decimal("1") / 30,
        "weekly": Decimal("1") / 4,
        "biweekly": Decimal("0.5"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("3"),
        "annually": Decimal("12"),
    }
    months_per_period = MONTHS_IN_PERIOD.get(repayment_frequency, Decimal("1"))

    # Total periods
    n_periods = Decimal(term_months) / months_per_period

    # Rate per period
    monthly_rate = (annual_rate / Decimal("100")) / Decimal("12")
    rate_per_period = monthly_rate * months_per_period

    if rate_per_period == 0:
        payment_per_period = principal / n_periods
    else:
        # PMT Formula
        payment_per_period = (
            principal
            * (rate_per_period * (1 + rate_per_period) ** n_periods)
            / ((1 + rate_per_period) ** n_periods - 1)
        )

    payment_per_period = payment_per_period.quantize(Decimal("0.01"), ROUND_HALF_UP)

    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []

    # Start first payment 1 period after start_date
    cur_date = advance_date(start_date, repayment_frequency)

    # Loop integer number of times? n_periods might be float if weekly?
    # Let's assume int for iteration, using ceiling or round logic matching fixed_term above
    loops = int(n_periods)

    for _ in range(loops):
        interest_due = (balance * rate_per_period).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        principal_due = (payment_per_period - interest_due).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        # Handle last payment rounding or if balance < principal_due
        if balance < principal_due:
            principal_due = balance
            total_due = principal_due + interest_due
        else:
            total_due = payment_per_period

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total_interest += interest_due

        schedule.append(
            {
                "due_date": cur_date.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest_due),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )

        cur_date = advance_date(cur_date, repayment_frequency)

    # Normalize "monthly_payment" for output
    output_monthly_payment = payment_per_period / months_per_period

    return {
        "term_months": term_months,
        "monthly_payment": float(output_monthly_payment),
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }


def reducing_fixed_payment(
    principal: Decimal,
    annual_rate: Decimal,
    payment_per_month: Decimal,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
    max_months: int = 360,
) -> Dict:
    """
    REDUCING BALANCE: Member selects PAYMENT → Calculate TERM
    """
    if payment_per_month <= 0:
        raise ValueError("Payment must be > 0")

    MONTHS_IN_PERIOD = {
        "daily": Decimal("1") / 30,
        "weekly": Decimal("1") / 4,
        "biweekly": Decimal("0.5"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("3"),
        "annually": Decimal("12"),
    }
    months_per_period = MONTHS_IN_PERIOD.get(repayment_frequency, Decimal("1"))

    # Convert monthly payment input to per-period payment
    payment_per_period = (payment_per_month * months_per_period).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )

    monthly_rate = (annual_rate / Decimal("100")) / Decimal("12")
    rate_per_period = monthly_rate * months_per_period

    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []

    # Start first payment 1 period after start_date
    cur_date = advance_date(start_date, repayment_frequency)

    months_elapsed = Decimal("0")  # Count in months for safety check

    # Safety max periods
    max_periods = max_months / float(months_per_period)
    periods_elapsed = 0

    while balance > Decimal("0.01") and periods_elapsed < max_periods:
        interest_due = (balance * rate_per_period).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        principal_due = (payment_per_period - interest_due).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        if principal_due > balance:
            principal_due = balance
            total_due = principal_due + interest_due
        else:
            total_due = payment_per_period

        # Prevent negative principal due if payment < interest
        if principal_due < 0:
            # We are not covering interest!
            # For this simple Calc, we can just let it grow or cap it.
            # Usually raises error in real systems calculate_term functions.
            pass

        balance = (balance - principal_due).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total_interest += interest_due

        schedule.append(
            {
                "due_date": cur_date.isoformat(),
                "principal_due": float(principal_due),
                "interest_due": float(interest_due),
                "total_due": float(total_due),
                "balance_after": float(balance),
            }
        )

        cur_date = advance_date(cur_date, repayment_frequency)
        months_elapsed += months_per_period
        periods_elapsed += 1

    term_months = int(months_elapsed.quantize(Decimal("1"), ROUND_HALF_UP))
    if term_months == 0 and len(schedule) > 0:
        term_months = 1  # At least one month if any schedule

    return {
        "term_months": term_months,
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }


# ======================================================================
# 3. INTERACTIVE MENU
# ======================================================================
def get_decimal(prompt: str) -> Decimal:
    while True:
        try:
            val = input(prompt).strip()
            if not val:
                raise ValueError
            return Decimal(val)
        except Exception:
            print("Please enter a valid number.")


def get_int(prompt: str) -> int:
    while True:
        try:
            val = input(prompt).strip()
            if not val:
                raise ValueError
            return int(val)
        except Exception:
            print("Please enter a valid integer.")


def get_numbered_choice(prompt: str, options: list) -> str:
    while True:
        print(prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        sel = input("→ ").strip()

        if sel.isdigit() and 1 <= int(sel) <= len(options):
            return options[int(sel) - 1].lower()

        lowered = [o.lower() for o in options]
        if sel.lower() in lowered:
            return sel.lower()

        print("Invalid choice – type the number or the full name.\n")


if __name__ == "__main__":
    print("\n=== SACCO Loan Calculator ===\n")

    # 1. Loan type
    loan_type = get_numbered_choice(
        "Select loan type:", ["Flat-rate", "Reducing (Diminishing) Balance"]
    )

    principal = get_decimal("\nPrincipal amount: ")
    annual_rate = get_decimal("Annual interest rate (e.g. 12.00): ")

    # 2. Frequency
    freq = get_numbered_choice(
        "Repayment frequency:",
        ["daily", "weekly", "biweekly", "monthly", "quarterly", "annually"],
    )

    # 3. Mode
    mode = get_numbered_choice(
        "Calculation mode:",
        ["Fixed monthly payment (calculate term)", "Fixed term (calculate payment)"],
    )

    # ------------------- FLAT-RATE -------------------
    if loan_type == "flat-rate":
        if mode.startswith("fixed monthly"):
            payment = get_decimal("Fixed payment per month: ")
            res = flat_rate_fixed_payment(
                principal, annual_rate, payment, repayment_frequency=freq
            )
            print("\n--- FLAT-RATE (Fixed Payment) ---")
            print(f"Term (months): {res['term_months']}")
        else:
            term = get_int("Desired term in months: ")
            res = flat_rate_fixed_term(
                principal, annual_rate, term, repayment_frequency=freq
            )
            print("\n--- FLAT-RATE (Fixed Term) ---")
            print(f"Monthly payment: {res['monthly_payment']:,.2f}")

    # ------------------- REDUCING BALANCE -------------------
    else:
        if mode.startswith("fixed monthly"):
            payment = get_decimal("Fixed payment per month: ")
            res = reducing_fixed_payment(
                principal, annual_rate, payment, repayment_frequency=freq
            )
            print("\n--- REDUCING BALANCE (Fixed Payment) ---")
            print(f"Term (months): {res['term_months']}")
        else:
            term = get_int("Desired term in months: ")
            res = reducing_fixed_term(
                principal, annual_rate, term, repayment_frequency=freq
            )
            print("\n--- REDUCING BALANCE (Fixed Term) ---")
            print(f"Monthly payment: {res['monthly_payment']:,.2f}")

    # ------------------- COMMON OUTPUT -------------------
    print(f"Total interest: {res['total_interest']:,.2f}")
    print(f"Total repayment: {res['total_repayment']:,.2f}")
    print(f"Payments made: {len(res['schedule'])}\n")

    # ------------------- FULL SCHEDULE -------------------
    print("FULL REPAYMENT SCHEDULE")
    print("-" * 90)
    print(
        f"{'#':>3} | {'Date':<12} | {'Principal':>12} | {'Interest':>10} | {'Total':>10} | {'Balance':>12}"
    )
    print("-" * 90)
    for i, entry in enumerate(res["schedule"], 1):
        print(
            f"{i:>3} | {entry['due_date']:<12} | "
            f"{entry['principal_due']:>12,.2f} | {entry['interest_due']:>10,.2f} | "
            f"{entry['total_due']:>10,.2f} | {entry['balance_after']:>12,.2f}"
        )
    print("-" * 90)
