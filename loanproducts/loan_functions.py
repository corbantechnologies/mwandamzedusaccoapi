# loans.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, List


# ----------------------------------------------------------------------
# 1. FLAT-RATE (interest on original principal)
# ----------------------------------------------------------------------
def flat_rate_fixed_payment(
    principal: Decimal,
    annual_rate: Decimal,
    payment_per_month: Decimal,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
    max_months: int = 360,
) -> Dict:
    """Fixed payment → calculate term."""
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
    payment_this_period = (payment_per_month * months_per_period).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )

    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []
    cur_date = start_date
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

        cur_date += payment_delta
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
    """Fixed term → calculate monthly payment."""
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

    return {
        "term_months": term_months,
        "monthly_payment": float(payment_per_period / months_per_period),
        "total_interest": float(total_interest),
        "total_repayment": float(total_repayment),
        "schedule": schedule,
    }


# ----------------------------------------------------------------------
# 2. REDUCING (DIMINISHING) BALANCE
# ----------------------------------------------------------------------
def reducing_fixed_payment(
    principal: Decimal,
    annual_rate: Decimal,
    payment_per_month: Decimal,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
    max_months: int = 360,
) -> Dict:
    """Fixed payment → calculate term."""
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
    balance = principal
    total_interest = Decimal("0")
    cur_date = start_date
    months_elapsed = Decimal("0")
    schedule: List[dict] = []

    payment_this_period = (payment_per_month * months_per_period).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )

    while balance > Decimal("0.01") and months_elapsed < max_months:
        due = cur_date

        interest_this_period = Decimal("0")
        calc_from = due - payment_delta
        while calc_from < due:
            calc_to = min(calc_from + relativedelta(days=1), due)
            days = (calc_to - calc_from).days
            time_frac = Decimal(days) / Decimal("365")
            period_int = (balance * rate * time_frac).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            interest_this_period += period_int
            calc_from = calc_to

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

        cur_date += payment_delta
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


def reducing_fixed_term(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date = date.today(),
    repayment_frequency: str = "monthly",
) -> Dict:
    """Fixed term → calculate monthly payment (PMT formula)."""
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

    payment_delta = DELTA[repayment_frequency]
    months_per_period = MONTHS_IN_PERIOD[repayment_frequency]

    rate = annual_rate / Decimal("100")
    r = rate / Decimal("12")
    n = Decimal(term_months)

    if r == 0:
        pmt = principal / n
    else:
        pmt = (
            principal
            * r
            * (Decimal("1") + r) ** n
            / ((Decimal("1") + r) ** n - Decimal("1"))
        )
    payment_per_month = pmt.quantize(Decimal("0.01"), ROUND_HALF_UP)

    payment_this_period = (payment_per_month * months_per_period).quantize(
        Decimal("0.01"), ROUND_HALF_UP
    )

    balance = principal
    total_interest = Decimal("0")
    schedule: List[dict] = []
    cur_date = start_date

    for _ in range(term_months):
        due = cur_date
        interest_this_period = (balance * r).quantize(Decimal("0.01"), ROUND_HALF_UP)
        interest_due = min(interest_this_period, payment_this_period)
        principal_due = payment_this_period - interest_due
        if balance < principal_due:
            principal_due = balance
            total_due = principal_due + interest_due
        else:
            total_due = payment_this_period

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
        cur_date += payment_delta

    return {
        "term_months": term_months,
        "monthly_payment": float(payment_per_month),
        "total_interest": float(total_interest.quantize(Decimal("0.01"))),
        "total_repayment": float(
            (principal + total_interest).quantize(Decimal("0.01"))
        ),
        "schedule": schedule,
    }


# ----------------------------------------------------------------------
# 3. NUMBERED MENU (type 1, 2, 3 …)
# ----------------------------------------------------------------------
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
    """Show numbered list and accept number or full text."""
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
    print("\n=== Simple Loan Calculator ===\n")

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
            print("\n--- FLAT-RATE (fixed payment) ---")
            print(f"Term (months)      : {res['term_months']}")
        else:
            term = get_int("Desired term in months: ")
            res = flat_rate_fixed_term(
                principal, annual_rate, term, repayment_frequency=freq
            )
            print("\n--- FLAT-RATE (fixed term) ---")
            print(f"Monthly payment    : {res['monthly_payment']:,}")

    # ------------------- REDUCING BALANCE -------------------
    else:
        if mode.startswith("fixed monthly"):
            payment = get_decimal("Fixed payment per month: ")
            res = reducing_fixed_payment(
                principal, annual_rate, payment, repayment_frequency=freq
            )
            print("\n--- REDUCING BALANCE (fixed payment) ---")
            print(f"Term (months)      : {res['term_months']}")
        else:
            term = get_int("Desired term in months: ")
            res = reducing_fixed_term(
                principal, annual_rate, term, repayment_frequency=freq
            )
            print("\n--- REDUCING BALANCE (fixed term) ---")
            print(f"Monthly payment    : {res['monthly_payment']:,}")

    # ------------------- COMMON OUTPUT -------------------
    print(f"Total interest     : {res['total_interest']:,}")
    print(f"Total repayment    : {res['total_repayment']:,}")
    print(f"Payments made      : {len(res['schedule'])}\n")

    # ------------------- FULL SCHEDULE -------------------
    print("FULL REPAYMENT SCHEDULE")
    print("-" * 80)
    print(
        f"{'#':>3} | {'Date':<12} | {'Principal':>10} | {'Interest':>10} | {'Total':>10} | {'Balance':>12}"
    )
    print("-" * 80)
    for i, entry in enumerate(res["schedule"], 1):
        print(
            f"{i:>3} | {entry['due_date']:<12} | "
            f"{entry['principal_due']:>10,.2f} | {entry['interest_due']:>10,.2f} | "
            f"{entry['total_due']:>10,.2f} | {entry['balance_after']:>12,.2f}"
        )
    print("-" * 80)
