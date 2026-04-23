# existingloans/services.py
import logging
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now
from financials.services import post_to_ledger

logger = logging.getLogger(__name__)


def process_existing_loan_disbursement_accounting(existing_loan):
    """
    Treats the adoption as a fresh disbursement of the combined debt.
    Debit: gl_principal_asset (The total debt being brought into the system)
    Credit: payment_method.gl_account (The bank source)
    """
    if existing_loan.posted_to_gl:
        return True

    if not existing_loan.payment_method or not existing_loan.gl_principal_asset:
        raise ValueError("Payment method and GL Principal Asset account must be set.")

    try:
        with transaction.atomic():
            bank_gl = existing_loan.payment_method.gl_account
            asset_gl = existing_loan.gl_principal_asset

            entries = [
                {"account": asset_gl, "debit": existing_loan.principal, "credit": 0},
                {"account": bank_gl, "debit": 0, "credit": existing_loan.principal},
            ]

            post_to_ledger(
                f"Existing Loan Disbursement: {existing_loan.account_number}",
                existing_loan.reference,
                entries,
                posting_date=existing_loan.created_at.date(),
            )

            existing_loan.posted_to_gl = True
            existing_loan.save(update_fields=["posted_to_gl"])
            return True

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Migration Disbursement Failure {existing_loan.reference}: {error_msg}"
        )
        existing_loan.accounting_error = f"{now()}: {error_msg}"
        existing_loan.save(update_fields=["accounting_error"])
        raise e
