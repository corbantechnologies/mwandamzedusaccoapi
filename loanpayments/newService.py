"""
newService.py — Targeted Installment Loan Repayment Service

Architectural upgrade over services.py:

  OLD: Sequential Waterfall
       → Iterates schedule rows in order, using overflow arithmetic to figure out
         where previous payments left off.

  NEW: Targeted Installment Lookup
       → Each payment optionally names a target installment_code.
       → The waterfall starts *at that specific row*, applying fee → interest → principal.
       → Any overflow spills into subsequent rows in chronological order (standard behaviour).
       → No target code? Falls back to the first unpaid row (identical to sequential).

Benefits:
  - Members can pay a future installment directly (e.g. pay month 6 before month 5).
  - Payment records link to a specific installment, giving a clean per-installment audit trail.
  - No overflow-arithmetic guesswork — row state is read directly from per-row tracking fields.
  - Fully backward compatible with schedules that have no target_installment_code on the payment.

Usage note:
  - Set payment.target_installment_code (if the field exists on the model) to enable targeting.
  - The field is read via getattr() so this service works without a model migration.
  - When the model gains the field, no code change is needed here.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils.timezone import now

from financials.services import post_to_ledger
from guarantors.services import update_guarantees_on_repayment

logger = logging.getLogger(__name__)


# ============================================================================
# INTERNAL HELPERS
# ============================================================================


def _row_remaining(row, bucket):
    """Return the remaining unpaid amount for a given bucket in a schedule row."""
    due_key = f"{bucket}_due"
    paid_key = f"{bucket}_paid"
    due = Decimal(str(row.get(due_key, 0)))
    paid = Decimal(str(row.get(paid_key, 0)))
    return max(Decimal("0"), due - paid)


def _apply_to_row(row, remaining):
    """
    Apply `remaining` payment amount to a single schedule row using the waterfall order:
      fee → interest → principal

    Mutates the row's tracking fields in-place.

    Returns:
        (take_f, take_i, take_p, leftover)  — all Decimal
    """
    take_f = min(remaining, _row_remaining(row, "fee"))
    remaining -= take_f

    take_i = min(remaining, _row_remaining(row, "interest"))
    remaining -= take_i

    take_p = min(remaining, _row_remaining(row, "principal"))
    remaining -= take_p

    row["fee_paid"] = float(Decimal(str(row.get("fee_paid", 0))) + take_f)
    row["interest_paid"] = float(Decimal(str(row.get("interest_paid", 0))) + take_i)
    row["principal_paid"] = float(Decimal(str(row.get("principal_paid", 0))) + take_p)
    row["amount_paid"] = float(
        Decimal(str(row.get("amount_paid", 0))) + take_f + take_i + take_p
    )

    if Decimal(str(row["amount_paid"])) >= Decimal(str(row.get("total_due", 0))):
        row["is_paid"] = True

    return take_f, take_i, take_p, remaining


def _find_start_index(schedule, target_code):
    """
    Return the schedule index to start the waterfall from.

    - If target_code is given and found (and unpaid) → that row's index.
    - If target_code given but not found → log a warning, fall back to first unpaid.
    - If no target_code → first unpaid row.
    """
    if target_code:
        for idx, row in enumerate(schedule):
            if row.get("installment_code") == target_code:
                if row.get("is_paid"):
                    raise ValueError(
                        f"Installment {target_code} is already fully paid. "
                        "Choose a different installment or make a regular payment."
                    )
                return idx
        # Code not found — warn and fall back
        logger.warning(
            f"target_installment_code '{target_code}' not found in schedule. "
            "Falling back to first unpaid row."
        )

    # First unpaid row
    for idx, row in enumerate(schedule):
        if not row.get("is_paid"):
            return idx

    return len(schedule)  # All rows are paid (edge case)


# ============================================================================
# CORE WATERFALL
# ============================================================================


def calculate_waterfall_split(loan_acc, amount_paid, target_installment_code=None):
    """
    Targeted Installment Waterfall.

    Applies `amount_paid` starting at the row identified by `target_installment_code`
    (or the first unpaid row when no target is given).  Overflow from a filled row
    cascades naturally into subsequent rows in schedule order.

    Per-row tracking fields (fee_paid, interest_paid, principal_paid, amount_paid,
    is_paid) are updated in-place.

    Returns:
        (p_total, i_total, f_total, Decimal("0"), schedule)
    """
    schedule = loan_acc.projection_snapshot.get("schedule", [])
    remaining = amount_paid
    p_total, i_total, f_total = Decimal("0"), Decimal("0"), Decimal("0")

    start_idx = _find_start_index(schedule, target_installment_code)

    for row in schedule[start_idx:]:
        if row.get("is_paid"):
            # Skip already-closed rows (e.g. out-of-order targeted payment that skipped a row)
            continue

        take_f, take_i, take_p, remaining = _apply_to_row(row, remaining)
        f_total += take_f
        i_total += take_i
        p_total += take_p

        if remaining <= 0:
            break

    # Any unallocated surplus → principal (overpayment edge case)
    if remaining > 0:
        p_total += remaining

    return p_total, i_total, f_total, Decimal("0"), schedule


# ============================================================================
# EARLY PAYOFF CALCULATOR  (unchanged logic, cleaner implementation)
# ============================================================================


def calculate_early_payoff_amounts(loan_acc):
    """
    Calculates the exact (principal, interest, fee) to fully close the loan today.

    Flat Rate:
        All interest and all fees must be paid — no waiver.
        Uses the waterfall on outstanding_balance.

    Reducing Balance:
        - Principal: full remaining principal.
        - Interest: only the remaining interest on the current (first unpaid) installment.
        - Fees: ALL unpaid fees across all remaining rows (non-negotiable).

    Uses per-row tracking fields for precision. Returns exact Decimal values.
    """
    product = loan_acc.product

    if product.interest_method == "Flat":
        p, i, f, _, _ = calculate_waterfall_split(
            loan_acc, loan_acc.outstanding_balance
        )
        return p, i, f

    # --- Reducing Balance ---
    remaining_principal = loan_acc.principal - loan_acc.total_principal_paid
    schedule = loan_acc.projection_snapshot.get("schedule", [])

    current_interest = Decimal("0")
    unpaid_fees = Decimal("0")
    is_first_unpaid = True

    rows_have_tracking = any("interest_paid" in row for row in schedule)

    if rows_have_tracking:
        for row in schedule:
            if row.get("is_paid"):
                continue

            if is_first_unpaid:
                # Charge only the remaining interest in the current row
                current_interest = _row_remaining(row, "interest")
                # Charge remaining fee in current row
                unpaid_fees += _row_remaining(row, "fee")
                is_first_unpaid = False
            else:
                # Future rows: interest waived, fees are NON-NEGOTIABLE
                unpaid_fees += Decimal(str(row.get("fee_due", 0)))

    else:
        # Legacy path (no tracking fields) — overflow arithmetic
        sum_closed = sum(
            Decimal(str(r["total_due"])) for r in schedule if r.get("is_paid")
        )
        overflow = loan_acc.total_amount_paid - sum_closed

        for row in schedule:
            if row.get("is_paid"):
                continue

            r_f = Decimal(str(row.get("fee_due", 0)))
            r_i = Decimal(str(row.get("interest_due", 0)))

            if is_first_unpaid:
                fee_consumed = min(overflow, r_f)
                overflow_after_fee = max(Decimal("0"), overflow - r_f)
                current_interest = max(Decimal("0"), r_i - min(overflow_after_fee, r_i))
                unpaid_fees += max(Decimal("0"), r_f - fee_consumed)
                is_first_unpaid = False
            else:
                unpaid_fees += r_f

    return remaining_principal, current_interest, unpaid_fees


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def process_loan_repayment_accounting(payment):
    """
    Targeted Installment Repayment Service.

    Orchestrates the full payment lifecycle:
      1. Determine distribution (principal / interest / fee / penalty).
      2. Update loan account balances and projection snapshot.
      3. Post to General Ledger.

    Supports an optional `target_installment_code` on the payment object.
    If set, the waterfall starts at that specific installment rather than the
    first chronologically unpaid row.

    Idempotent: safe to call multiple times — exits early if already processed.
    """
    if payment.transaction_status != "Completed":
        return False
    if payment.posted_to_gl and payment.balance_updated:
        return True

    loan_acc = payment.loan_account
    product = loan_acc.product

    # Read optional targeting field (graceful degradation if field doesn't exist yet)
    target_code = getattr(payment, "target_installment_code", None)

    try:
        with transaction.atomic():

            # ----------------------------------------------------------------
            # 1. DETERMINE DISTRIBUTION
            # ----------------------------------------------------------------
            principal = interest = fee = penalty = Decimal("0")
            updated_schedule = loan_acc.projection_snapshot.get("schedule", [])

            if payment.repayment_type == "Penalty Payment":
                penalty = payment.amount

            elif payment.repayment_type == "Early Settlement":
                principal, interest, fee = calculate_early_payoff_amounts(loan_acc)

                # Validation (tolerance for floating point)
                expected_total = principal + interest + fee
                if abs(payment.amount - expected_total) > Decimal("0.01"):
                    raise ValueError(
                        f"Early Settlement requires exactly {expected_total}. "
                        f"Received {payment.amount}."
                    )

                # --- Accrual Reset ---
                # Sets total_interest_accrued so that outstanding_balance = 0 after save().
                # Formula: outstanding = (principal + interest_accrued + fee) - total_paid = 0
                new_total_paid = loan_acc.total_amount_paid + payment.amount

                if product.interest_method == "Flat":
                    loan_acc.total_interest_accrued = (
                        new_total_paid - loan_acc.principal - loan_acc.processing_fee
                    )
                else:
                    rows_have_tracking = any(
                        "interest_paid" in row for row in updated_schedule
                    )
                    if rows_have_tracking:
                        # Sum interest across ALL rows — including partially-paid ones
                        interest_recognised = sum(
                            Decimal(str(row.get("interest_paid", 0)))
                            for row in updated_schedule
                        )
                        loan_acc.total_interest_accrued = interest_recognised + interest
                    else:
                        # Legacy fallback
                        interest_paid_prev = (
                            loan_acc.total_amount_paid - loan_acc.total_principal_paid
                        )
                        loan_acc.total_interest_accrued = interest_paid_prev + interest

                # Mark all rows paid, fill tracking fields for future-waived rows
                for row in updated_schedule:
                    row["is_paid"] = True
                    row.setdefault("fee_paid", row.get("fee_due", 0))
                    row.setdefault("interest_paid", row.get("interest_due", 0))
                    row.setdefault("principal_paid", row.get("principal_due", 0))
                    row.setdefault("amount_paid", row.get("total_due", 0))

                loan_acc.status = "Closed"

            else:
                # Regular / Partial / Interest Only — targeted waterfall
                principal, interest, fee, _, updated_schedule = (
                    calculate_waterfall_split(
                        loan_acc, payment.amount, target_installment_code=target_code
                    )
                )

            # ----------------------------------------------------------------
            # 2. OPERATIONAL UPDATES
            # ----------------------------------------------------------------
            if not payment.balance_updated:
                loan_acc.total_principal_paid += principal
                loan_acc.total_amount_paid += principal + interest + fee

                loan_acc.projection_snapshot["schedule"] = updated_schedule
                loan_acc.save()

                if principal > 0:
                    update_guarantees_on_repayment(loan_acc, principal)

                payment.balance_updated = True

            # ----------------------------------------------------------------
            # 3. GENERAL LEDGER POSTING
            # ----------------------------------------------------------------
            if not payment.posted_to_gl:
                bank_gl = payment.payment_method.gl_account

                entries = [
                    {"account": bank_gl, "debit": payment.amount, "credit": 0},
                    {
                        "account": product.gl_principal_asset,
                        "debit": 0,
                        "credit": principal,
                    },
                    {
                        "account": product.gl_interest_revenue,
                        "debit": 0,
                        "credit": interest,
                    },
                    {
                        "account": product.gl_processing_fee_revenue,
                        "debit": 0,
                        "credit": fee,
                    },
                    {
                        "account": product.gl_penalty_revenue,
                        "debit": 0,
                        "credit": penalty,
                    },
                ]

                description = payment.repayment_type
                if target_code:
                    description += f" [{target_code}]"
                description += f": {loan_acc.account_number}"

                post_to_ledger(
                    description,
                    payment.reference,
                    entries,
                    posting_date=payment.payment_date.date(),
                )
                payment.posted_to_gl = True

            payment.accounting_error = None
            payment.save(
                update_fields=["balance_updated", "posted_to_gl", "accounting_error"]
            )
            return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"REPAYMENT FAILURE {payment.reference}: {error_msg}")
        type(payment).objects.filter(id=payment.id).update(
            accounting_error=f"{now()}: {error_msg}"
        )
        raise e
