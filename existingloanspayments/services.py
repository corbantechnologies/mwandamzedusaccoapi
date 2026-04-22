"""
Existing Loan Payment Services
This is very simple, we just need to update the existing loan balance
We also need to post to the general ledger
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now
from financials.services import post_to_ledger

logger = logging.getLogger(__name__)


def process_existing_loan_payment_accounting(payment):
    """
    Repayment logic for Adopted Loans.
    Since 'principal' includes interest, ALL payments reduce the outstanding balance.
    """
    if payment.transaction_status != "Completed":
        return False
    if payment.posted_to_gl and payment.balance_updated:
        return True

    loan = payment.existing_loan

    try:
        with transaction.atomic():
            # --- 1. OPERATIONAL UPDATES ---
            if not payment.balance_updated:
                # Update specific tracking counters for reporting/audit
                if payment.repayment_type == "Interest Only":
                    loan.total_interest_paid += payment.amount
                elif payment.repayment_type == "Penalty Payment":
                    loan.total_penalties_paid += payment.amount

                # EVERY cent collected reduces the 'Fresh Start' principal
                loan.total_amount_paid += payment.amount

                # Model save() recalculates outstanding_balance = principal - total_amount_paid
                loan.save()
                payment.balance_updated = True

            # --- 2. GENERAL LEDGER POSTING ---
            if not payment.posted_to_gl:
                bank_gl = payment.payment_method.gl_account

                # Route to GL based on admin label
                if payment.repayment_type == "Interest Only":
                    credit_acc = loan.gl_interest_revenue
                elif payment.repayment_type == "Penalty Payment":
                    credit_acc = loan.gl_penalty_revenue
                else:
                    # Regular/Partial/Clearance/Early Settlement goes to Principal Asset
                    credit_acc = loan.gl_principal_asset

                if not credit_acc:
                    raise ValueError(
                        f"GL account for {payment.repayment_type} is not configured."
                    )

                entries = [
                    {"account": bank_gl, "debit": payment.amount, "credit": 0},
                    {"account": credit_acc, "debit": 0, "credit": payment.amount},
                ]

                post_to_ledger(
                    f"Existing Repayment ({payment.repayment_type}): {loan.account_number}",
                    payment.reference,
                    entries,
                    posting_date=payment.created_at.date(),
                )
                payment.posted_to_gl = True

            payment.accounting_error = None
            payment.save(
                update_fields=["balance_updated", "posted_to_gl", "accounting_error"]
            )
            return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Existing Payment Failure {payment.reference}: {error_msg}")
        # Use .update() to avoid triggering the model's save() logic/recalcs again
        type(payment).objects.filter(id=payment.id).update(
            accounting_error=f"{now()}: {error_msg}"
        )
        raise e
