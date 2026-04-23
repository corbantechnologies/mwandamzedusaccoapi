import logging
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now
from financials.services import post_to_ledger
from guarantors.services import update_guarantees_on_repayment
from loanpenalties.models import LoanPenalty

logger = logging.getLogger(__name__)


def process_loan_repayment_accounting(payment):
    """
    Main Repayment Service:
    - Uses repayment_type as the primary Source of Truth.
    - Handles Waterfall (Regular/Partial), Penalty, and Early Settlement.
    - Includes 'Accrual Reset' to ensure outstanding_balance hits zero on settlement.
    """
    if payment.transaction_status != "Completed":
        return False
    if payment.posted_to_gl and payment.balance_updated:
        return True

    loan_acc = payment.loan_account
    product = loan_acc.product

    try:
        with transaction.atomic():
            # --- 1. DETERMINE DISTRIBUTION ---
            principal, interest, fee, penalty = (
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
            )
            updated_schedule = loan_acc.projection_snapshot.get("schedule", [])

            if payment.repayment_type == "Penalty Payment":
                # GL accounting leg: full payment amount hits penalty revenue
                penalty = payment.amount

                # OPERATIONAL RESOLUTION: FIFO clearance of Pending LoanPenalty records.
                # Only "Pending" penalties are targeted — Paid and Waived are untouched.
                pending_penalties = loan_acc.penalties.filter(
                    status="Pending"
                ).order_by("created_at")

                remaining_cash = payment.amount
                for pen_rec in pending_penalties:
                    if remaining_cash <= Decimal("0"):
                        break

                    pen_original = Decimal(str(pen_rec.amount or 0))
                    pen_already_paid = Decimal(str(pen_rec.amount_paid or 0))
                    pen_balance = pen_original - pen_already_paid

                    if pen_balance <= Decimal("0"):
                        # Already fully covered (edge case guard), skip
                        continue

                    if remaining_cash >= pen_balance:
                        # Full clearance of this penalty record
                        remaining_cash -= pen_balance
                        pen_rec.amount_paid = pen_original
                        pen_rec.status = "Paid"
                        pen_rec.save(update_fields=["amount_paid", "status"])
                    else:
                        # Partial clearance: record what was paid, amount stays intact
                        pen_rec.amount_paid = pen_already_paid + remaining_cash
                        pen_rec.save(update_fields=["amount_paid"])
                        remaining_cash = Decimal("0")

                # Penalty payments are fully outside the loan amortization contract.
                # They do not reduce outstanding_balance or affect any principal/interest totals.

            elif payment.repayment_type == "Early Settlement":
                # GUARD: Block early settlement if there are outstanding penalties.
                # Member must use 'Loan Clearance' to settle both together.
                pending_penalty_count = loan_acc.penalties.filter(
                    status="Pending"
                ).count()
                if pending_penalty_count > 0:
                    raise ValueError(
                        f"This loan has {pending_penalty_count} outstanding penalty(ies). "
                        "Use 'Loan Clearance' to settle the loan and all penalties together."
                    )

                # Calculate required payoff amounts using unified calculator
                principal, interest, fee = calculate_early_payoff_amounts(loan_acc)

                # Validation with tolerance for floating point precision
                expected_total = principal + interest + fee
                if abs(payment.amount - expected_total) > Decimal("0.01"):
                    raise ValueError(
                        f"Early Settlement requires exactly {expected_total}. Received {payment.amount}"
                    )

                # --- Accrual Reset ---
                # Ensures total_interest_accrued is set so outstanding_balance hits 0.00 on save().
                # outstanding_balance = (principal + total_interest_accrued + processing_fee) - total_amount_paid
                # Setting total_interest_accrued = new_total_paid - principal - processing_fee guarantees 0.

                new_total_paid = loan_acc.total_amount_paid + payment.amount

                if product.interest_method == "Flat":
                    # Flat Rate: all interest must be paid on settlement.
                    # Derive total_interest_accrued algebraically so the balance zeroes exactly.
                    loan_acc.total_interest_accrued = (
                        new_total_paid - loan_acc.principal - loan_acc.processing_fee
                    )
                else:
                    # Reducing Balance: only current period's interest is charged; future interest is waived.
                    # Prefer row-level tracked interest_paid (new system) for precision.
                    # Fall back to amount-based approximation for legacy rows without tracking fields.
                    rows_have_tracking = any(
                        "interest_paid" in row for row in updated_schedule
                    )
                    if rows_have_tracking:
                        # Sum interest already recognised across ALL rows —
                        # including partially-paid rows where interest was
                        # fully settled even though principal is still outstanding.
                        interest_already_recognised = sum(
                            Decimal(str(row.get("interest_paid", 0)))
                            for row in updated_schedule
                        )
                        loan_acc.total_interest_accrued = (
                            interest_already_recognised + interest
                        )
                    else:
                        # Legacy path: derive from paid amounts (may include rounding error)
                        interest_paid_previously = (
                            loan_acc.total_amount_paid - loan_acc.total_principal_paid
                        )
                        loan_acc.total_interest_accrued = (
                            interest_paid_previously + interest
                        )

                # Mark entire schedule as paid and populate tracking fields for settled rows
                for row in updated_schedule:
                    row["is_paid"] = True
                    # Ensure tracking fields exist (may still be 0 for future-waived rows)
                    if "fee_paid" not in row:
                        row["fee_paid"] = row.get("fee_due", 0)
                    if "interest_paid" not in row:
                        row["interest_paid"] = row.get("interest_due", 0)
                    if "principal_paid" not in row:
                        row["principal_paid"] = row.get("principal_due", 0)
                    if "amount_paid" not in row:
                        row["amount_paid"] = row.get("total_due", 0)

                loan_acc.status = "Closed"

            elif payment.repayment_type == "Loan Clearance":
                # Loan Clearance = Early Settlement + all pending penalties in one transaction.
                # Uses the same interest-method-aware calculation as Early Settlement.
                principal, interest, fee = calculate_early_payoff_amounts(loan_acc)

                # Aggregate total outstanding penalty balance
                pending_penalties = loan_acc.penalties.filter(
                    status="Pending"
                ).order_by("created_at")
                pending_penalty_total = sum(
                    max(
                        Decimal("0"),
                        Decimal(str(p.amount or 0)) - Decimal(str(p.amount_paid or 0)),
                    )
                    for p in pending_penalties
                )
                penalty = pending_penalty_total

                # Validation: amount must cover settlement + all penalties
                expected_total = principal + interest + fee + pending_penalty_total
                if abs(payment.amount - expected_total) > Decimal("0.01"):
                    raise ValueError(
                        f"Loan Clearance requires exactly {expected_total} "
                        f"({principal} principal + {interest} interest + {fee} fees + "
                        f"{pending_penalty_total} penalties). Received {payment.amount}"
                    )

                # --- Accrual Reset (same logic as Early Settlement) ---
                new_total_paid = loan_acc.total_amount_paid + principal + interest + fee

                if product.interest_method == "Flat":
                    loan_acc.total_interest_accrued = (
                        new_total_paid - loan_acc.principal - loan_acc.processing_fee
                    )
                else:
                    rows_have_tracking = any(
                        "interest_paid" in row for row in updated_schedule
                    )
                    if rows_have_tracking:
                        interest_already_recognised = sum(
                            Decimal(str(row.get("interest_paid", 0)))
                            for row in updated_schedule
                        )
                        loan_acc.total_interest_accrued = (
                            interest_already_recognised + interest
                        )
                    else:
                        interest_paid_previously = (
                            loan_acc.total_amount_paid - loan_acc.total_principal_paid
                        )
                        loan_acc.total_interest_accrued = (
                            interest_paid_previously + interest
                        )

                # Mark entire schedule as paid
                for row in updated_schedule:
                    row["is_paid"] = True
                    if "fee_paid" not in row:
                        row["fee_paid"] = row.get("fee_due", 0)
                    if "interest_paid" not in row:
                        row["interest_paid"] = row.get("interest_due", 0)
                    if "principal_paid" not in row:
                        row["principal_paid"] = row.get("principal_due", 0)
                    if "amount_paid" not in row:
                        row["amount_paid"] = row.get("total_due", 0)

                loan_acc.status = "Closed"

                # FIFO clearance of all pending penalties
                remaining_cash = pending_penalty_total
                for pen_rec in pending_penalties:
                    if remaining_cash <= Decimal("0"):
                        break
                    pen_original = Decimal(str(pen_rec.amount or 0))
                    pen_already_paid = Decimal(str(pen_rec.amount_paid or 0))
                    pen_balance = pen_original - pen_already_paid
                    if pen_balance <= Decimal("0"):
                        continue
                    if remaining_cash >= pen_balance:
                        remaining_cash -= pen_balance
                        pen_rec.amount_paid = pen_original
                        pen_rec.status = "Paid"
                        pen_rec.save(update_fields=["amount_paid", "status"])
                    else:
                        pen_rec.amount_paid = pen_already_paid + remaining_cash
                        pen_rec.save(update_fields=["amount_paid"])
                        remaining_cash = Decimal("0")

            else:
                # Default Waterfall logic for Regular, Partial, and Individual repayments
                principal, interest, fee, _, updated_schedule = (
                    calculate_waterfall_split(loan_acc, payment.amount)
                )

            # --- 2. OPERATIONAL UPDATES ---
            if not payment.balance_updated:
                # Penalty payments have no impact on loan principal/interest/fee balances.
                # Only update loan account totals for non-penalty repayment types.
                if payment.repayment_type != "Penalty Payment":
                    loan_acc.total_principal_paid += principal
                    loan_acc.total_amount_paid += principal + interest + fee

                    # Persist updated schedule (is_paid flags + per-row payment tracking)
                    loan_acc.projection_snapshot["schedule"] = updated_schedule

                    # save() triggers: total_loan_amount recalc + outstanding_balance recalc
                    loan_acc.save()

                    # Proportionally release guarantor liability based on principal reduction
                    if principal > 0:
                        update_guarantees_on_repayment(loan_acc, principal)

                payment.balance_updated = True

            # --- 3. GENERAL LEDGER POSTING ---
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

                # Centralized service handles filtering zero-legs and batch creation
                post_to_ledger(
                    f"{payment.repayment_type}: {loan_acc.account_number}",
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


def calculate_early_payoff_amounts(loan_acc):
    """
    Calculates the exact (principal, interest, fee) required to fully close the loan today.

    Flat Rate:
      All interest and all fees must be paid — no waiver. Uses the waterfall on
      outstanding_balance (same as a regular full payment).

    Reducing Balance:
      - Principal: full remaining principal balance.
      - Interest: only the current period's remaining interest (future interest is waived).
      - Fees: ALL unpaid processing fees are mandatory regardless of interest waiver.

    Uses per-row payment tracking fields (fee_paid, interest_paid) when available.
    Falls back to overflow arithmetic for legacy rows without those fields.
    """
    product = loan_acc.product

    if product.interest_method == "Flat":
        # Flat Rate: Run waterfall on outstanding_balance — all buckets must be settled.
        p, i, f, _, _ = calculate_waterfall_split(
            loan_acc, loan_acc.outstanding_balance
        )
        return p, i, f

    else:
        # Reducing Balance: waive future interest, but ALL fees are mandatory.
        remaining_principal = loan_acc.principal - loan_acc.total_principal_paid
        schedule = loan_acc.projection_snapshot.get("schedule", [])

        rows_have_tracking = any("interest_paid" in row for row in schedule)

        if rows_have_tracking:
            # --- New path: read directly from per-row tracking fields ---
            current_interest = Decimal("0")
            unpaid_fees = Decimal("0")
            is_first_unpaid = True

            for row in schedule:
                if row.get("is_paid"):
                    continue

                fee_paid_in_row = Decimal(str(row.get("fee_paid", 0)))

                if is_first_unpaid:
                    # Current active row: charge remaining interest + remaining fee
                    interest_paid_in_row = Decimal(str(row.get("interest_paid", 0)))
                    current_interest = max(
                        Decimal("0"),
                        Decimal(str(row.get("interest_due", 0))) - interest_paid_in_row,
                    )
                    unpaid_fees += max(
                        Decimal("0"),
                        Decimal(str(row.get("fee_due", 0))) - fee_paid_in_row,
                    )
                    is_first_unpaid = False
                else:
                    # Future rows: interest waived, but fees are NON-NEGOTIABLE.
                    unpaid_fees += Decimal(str(row.get("fee_due", 0)))

        else:
            # --- Legacy path: recompute overflow from running totals ---
            sum_closed_rows = sum(
                Decimal(str(r["total_due"])) for r in schedule if r.get("is_paid")
            )
            overflow = loan_acc.total_amount_paid - sum_closed_rows

            current_interest = Decimal("0")
            unpaid_fees = Decimal("0")
            is_first_unpaid = True

            for row in schedule:
                if row.get("is_paid"):
                    continue

                r_f = Decimal(str(row.get("fee_due", 0)))
                r_i = Decimal(str(row.get("interest_due", 0)))

                if is_first_unpaid:
                    # Waterfall order: fee first, then interest
                    fee_overflow_consumed = min(overflow, r_f)
                    overflow_after_fee = max(Decimal("0"), overflow - r_f)

                    current_fee_remaining = max(
                        Decimal("0"), r_f - fee_overflow_consumed
                    )
                    interest_overflow_consumed = min(overflow_after_fee, r_i)
                    current_interest = max(
                        Decimal("0"), r_i - interest_overflow_consumed
                    )

                    unpaid_fees += current_fee_remaining
                    is_first_unpaid = False
                else:
                    # Future rows: full fee is due
                    unpaid_fees += r_f

        return remaining_principal, current_interest, unpaid_fees


def calculate_waterfall_split(loan_acc, amount_paid):
    """
    Core Greedy Waterfall algorithm.

    Processes installments in order (fee → interest → principal per row),
    respecting any overflow from amounts already paid toward the current row.

    Per-row tracking fields are updated in-place on the schedule rows:
      - fee_paid, interest_paid, principal_paid: cumulative contributions per bucket
      - amount_paid: total cumulative amount applied to this row
      - is_paid: True once amount_paid >= total_due for the row
    """
    schedule = loan_acc.projection_snapshot.get("schedule", [])
    remaining = amount_paid
    p_total, i_total, f_total = Decimal("0"), Decimal("0"), Decimal("0")

    # Overflow = amount already paid that has not yet closed a row (sitting mid-row)
    sum_closed_rows = sum(
        Decimal(str(r["total_due"])) for r in schedule if r.get("is_paid")
    )
    previous_overflow = loan_acc.total_amount_paid - sum_closed_rows

    for row in schedule:
        if row.get("is_paid"):
            continue

        r_f = Decimal(str(row.get("fee_due", 0)))
        r_i = Decimal(str(row.get("interest_due", 0)))
        r_p = Decimal(str(row.get("principal_due", 0)))

        # Existing per-row tracked amounts (cumulative from prior payments)
        row_fee_paid = Decimal(str(row.get("fee_paid", 0)))
        row_interest_paid = Decimal(str(row.get("interest_paid", 0)))
        row_principal_paid = Decimal(str(row.get("principal_paid", 0)))
        row_amount_paid_so_far = Decimal(str(row.get("amount_paid", 0)))

        # --- Fee bucket ---
        f_gap = max(Decimal("0"), r_f - previous_overflow)
        take_f = min(remaining, f_gap)
        f_total += take_f
        remaining -= take_f
        previous_overflow = max(Decimal("0"), previous_overflow - r_f)

        # --- Interest bucket ---
        i_gap = max(Decimal("0"), r_i - previous_overflow)
        take_i = min(remaining, i_gap)
        i_total += take_i
        remaining -= take_i
        previous_overflow = max(Decimal("0"), previous_overflow - r_i)

        # --- Principal bucket ---
        p_gap = max(Decimal("0"), r_p - previous_overflow)
        take_p = min(remaining, p_gap)
        p_total += take_p
        remaining -= take_p
        previous_overflow = Decimal("0")

        # Update per-row tracking (additive — only adds what THIS payment contributed)
        row["fee_paid"] = float(row_fee_paid + take_f)
        row["interest_paid"] = float(row_interest_paid + take_i)
        row["principal_paid"] = float(row_principal_paid + take_p)
        row["amount_paid"] = float(row_amount_paid_so_far + take_f + take_i + take_p)

        # Mark row as paid when the cumulative amount_paid covers total_due
        if Decimal(str(row["amount_paid"])) >= Decimal(str(row.get("total_due", 0))):
            row["is_paid"] = True

        if remaining <= 0:
            break

    # Any unallocated remainder goes to principal (e.g., overpayment edge cases)
    if remaining > 0:
        p_total += remaining

    return p_total, i_total, f_total, Decimal("0"), schedule
