"""
Management command: backfill_projection_payments

Purpose
-------
Adds per-row payment-tracking fields (fee_paid, interest_paid, principal_paid,
amount_paid) to the projection_snapshot.schedule of every active LoanAccount by
replaying all completed, balance-updated payments through the waterfall engine.

Why
---
These fields are used by the new calculate_early_payoff_amounts() and the
Reducing-Balance Accrual Reset to determine exactly how much of each installment
has been paid — without having to re-derive it from running totals (which was the
source of the early-settlement balance discrepancy bug).

What it touches
---------------
- loan_account.projection_snapshot  (updated)
- loan_application.projection_snapshot  (NEVER modified — left for member reference)

Usage
-----
    python manage.py backfill_projection_payments
    python manage.py backfill_projection_payments --account LN2620024528
    python manage.py backfill_projection_payments --dry-run
"""

import copy
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from loanaccounts.models import LoanAccount
from loanapplications.utils import generate_installment_code

# ---------------------------------------------------------------------------
# Standalone waterfall engine
# Mirrors calculate_waterfall_split() but operates on an explicit schedule +
# running paid amount, so we can replay payments sequentially without a real
# LoanAccount object being mutated mid-loop.
# ---------------------------------------------------------------------------


def _waterfall_engine(schedule, amount_paid, total_previously_paid):
    """
    Run one payment of `amount_paid` through the schedule.

    Args:
        schedule: list of row dicts (mutated in-place with tracking fields)
        amount_paid: Decimal — amount being applied in this step
        total_previously_paid: Decimal — sum of all prior payments (for overflow)

    Returns:
        (p_total, i_total, f_total) Decimal split for this payment
    """
    remaining = amount_paid
    p_total, i_total, f_total = Decimal("0"), Decimal("0"), Decimal("0")

    sum_closed = sum(Decimal(str(r["total_due"])) for r in schedule if r.get("is_paid"))
    previous_overflow = total_previously_paid - sum_closed

    for row in schedule:
        if row.get("is_paid"):
            continue

        r_f = Decimal(str(row.get("fee_due", 0)))
        r_i = Decimal(str(row.get("interest_due", 0)))
        r_p = Decimal(str(row.get("principal_due", 0)))

        row_fee_paid = Decimal(str(row.get("fee_paid", 0)))
        row_interest_paid = Decimal(str(row.get("interest_paid", 0)))
        row_principal_paid = Decimal(str(row.get("principal_paid", 0)))
        row_amount_paid_so_far = Decimal(str(row.get("amount_paid", 0)))

        # Fee bucket
        f_gap = max(Decimal("0"), r_f - previous_overflow)
        take_f = min(remaining, f_gap)
        f_total += take_f
        remaining -= take_f
        previous_overflow = max(Decimal("0"), previous_overflow - r_f)

        # Interest bucket
        i_gap = max(Decimal("0"), r_i - previous_overflow)
        take_i = min(remaining, i_gap)
        i_total += take_i
        remaining -= take_i
        previous_overflow = max(Decimal("0"), previous_overflow - r_i)

        # Principal bucket
        p_gap = max(Decimal("0"), r_p - previous_overflow)
        take_p = min(remaining, p_gap)
        p_total += take_p
        remaining -= take_p
        previous_overflow = Decimal("0")

        # Persist per-row tracking
        row["fee_paid"] = float(row_fee_paid + take_f)
        row["interest_paid"] = float(row_interest_paid + take_i)
        row["principal_paid"] = float(row_principal_paid + take_p)
        row["amount_paid"] = float(row_amount_paid_so_far + take_f + take_i + take_p)

        if Decimal(str(row["amount_paid"])) >= Decimal(str(row.get("total_due", 0))):
            row["is_paid"] = True

        if remaining <= 0:
            break

    if remaining > 0:
        p_total += remaining

    return p_total, i_total, f_total


def _get_pristine_schedule(loan_account):
    """
    Return a fresh copy of the original schedule with no payment tracking.
    Prefers the loan application's snapshot (source of truth).
    Falls back to the loan account's snapshot (admin-created loans).
    """
    application = getattr(loan_account, "application", None)
    if application and application.projection_snapshot:
        source = application.projection_snapshot.get("schedule", [])
    else:
        source = loan_account.projection_snapshot.get("schedule", [])

    pristine = copy.deepcopy(source)

    # Reset all payment tracking — keep structure/dates/amounts intact
    for row in pristine:
        row["is_paid"] = False
        row["fee_paid"] = 0.0
        row["interest_paid"] = 0.0
        row["principal_paid"] = 0.0
        row["amount_paid"] = 0.0
        # Ensure installment_code exists — will retroactively add to existing loans
        if "installment_code" not in row:
            row["installment_code"] = generate_installment_code()

    return pristine


def _replay_payments(loan_account, schedule, stdout, dry_run):
    """
    Replay all completed, balance-updated payments through the waterfall.
    Mutates `schedule` in-place.
    Returns False if any payment could not be replayed cleanly.
    """
    payments = loan_account.loan_payments.filter(
        transaction_status="Completed", balance_updated=True
    ).order_by("payment_date", "created_at")

    running_total_paid = Decimal("0")

    for payment in payments:
        amount = Decimal(str(payment.amount))

        if payment.repayment_type == "Early Settlement":
            # Mark all remaining rows as paid; set tracking fields to their full values
            for row in schedule:
                if not row.get("is_paid"):
                    row["is_paid"] = True
                    # For settlement rows we don't backfill granular splits —
                    # the balance fix works from total_interest_accrued recalc.
                    # But we do set amount_paid so rows look consistent.
                    total_due = Decimal(str(row.get("total_due", 0)))
                    already_paid = Decimal(str(row.get("amount_paid", 0)))
                    remainder = max(Decimal("0"), total_due - already_paid)
                    row["amount_paid"] = float(already_paid + remainder)

            running_total_paid += amount

        elif payment.repayment_type == "Penalty Payment":
            # Penalties don't touch the installment schedule
            pass

        else:
            # Regular / Partial / Interest Only — run through waterfall
            _waterfall_engine(schedule, amount, running_total_paid)
            running_total_paid += amount

    return True


class Command(BaseCommand):
    help = (
        "Backfills per-row payment tracking fields (fee_paid, interest_paid, "
        "principal_paid, amount_paid) in loan_account.projection_snapshot.schedule "
        "by replaying all completed payments through the waterfall engine."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--account",
            type=str,
            help="Restrict to a single loan account number (e.g. LN2620024528).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Compute changes but do not write to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        account_filter = options.get("account")

        qs = LoanAccount.objects.select_related(
            "application", "product"
        ).prefetch_related("loan_payments")

        if account_filter:
            qs = qs.filter(account_number=account_filter)

        total = qs.count()
        if total == 0:
            self.stdout.write(
                self.style.WARNING("No loan accounts matched the filter.")
            )
            return

        mode = "[DRY RUN] " if dry_run else ""
        self.stdout.write(f"{mode}Backfilling {total} loan account(s)...")

        success_count = 0
        error_count = 0

        for loan_account in qs.iterator(chunk_size=100):
            try:
                if not loan_account.projection_snapshot:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  SKIP {loan_account.account_number}: no projection_snapshot."
                        )
                    )
                    continue

                pristine = _get_pristine_schedule(loan_account)
                if not pristine:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  SKIP {loan_account.account_number}: empty schedule."
                        )
                    )
                    continue

                _replay_payments(loan_account, pristine, self.stdout, dry_run)

                if not dry_run:
                    with transaction.atomic():
                        loan_account.projection_snapshot["schedule"] = pristine
                        # Use update() to avoid triggering balance recalc in save()
                        LoanAccount.objects.filter(pk=loan_account.pk).update(
                            projection_snapshot=loan_account.projection_snapshot
                        )

                success_count += 1
                self.stdout.write(
                    f"  {'[DRY] ' if dry_run else ''}OK {loan_account.account_number}"
                )

            except Exception as e:
                error_count += 1
                self.stderr.write(
                    self.style.ERROR(f"  FAIL {loan_account.account_number}: {e}")
                )

        summary = (
            f"\n{mode}Done. "
            f"Processed: {success_count}/{total}  |  Errors: {error_count}"
        )
        if error_count:
            self.stdout.write(self.style.ERROR(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
