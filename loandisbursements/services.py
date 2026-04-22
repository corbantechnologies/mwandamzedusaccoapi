import logging
from django.db import transaction
from django.utils.timezone import now
from financials.services import post_to_ledger

logger = logging.getLogger(__name__)


def process_loan_disbursement_accounting(disbursement):
    """
    Refactored Disbursement Service:
    1. Records the raw principal lent out as a Receivable Asset.
    2. Records the cash outflow from the Bank.
    3. Updates the loan account status to 'Funded'.

    Note: Interest and Processing Fees are NOT recognized here.
    They are recognized period-by-period during repayment.
    """

    if disbursement.transaction_status != "Completed":
        logger.warning(
            f"Disbursement {disbursement.reference} not Completed. Skipping."
        )
        return False

    if disbursement.posted_to_gl and disbursement.balance_updated:
        return True

    loan_acc = disbursement.loan_account
    product = loan_acc.product

    try:
        with transaction.atomic():
            # 1. Update Operational State
            if not disbursement.balance_updated:
                # Update status to Funded to trigger activation logic
                loan_acc.status = "Funded"
                loan_acc.save(update_fields=["status"])
                disbursement.balance_updated = True

            # 2. Post to General Ledger
            if not disbursement.posted_to_gl:
                if (
                    not disbursement.payment_method
                    or not disbursement.payment_method.gl_account
                ):
                    raise ValueError(
                        f"No GL Account linked to Payment Method: {disbursement.payment_method}"
                    )

                bank_gl = disbursement.payment_method.gl_account
                principal_asset_gl = product.gl_principal_asset

                description = f"Loan Disbursement: {loan_acc.account_number} | Member: {loan_acc.member.member_no}"

                # Simple Two-Leg Entry: Assets exchanging form (Cash -> Loan Receivable)
                entries = [
                    # ASSET: Increase Loans to Members (Debit)
                    {
                        "account": principal_asset_gl,
                        "debit": disbursement.amount,
                        "credit": 0,
                    },
                    # ASSET: Decrease Bank/Cash (Credit)
                    {"account": bank_gl, "debit": 0, "credit": disbursement.amount},
                ]

                post_to_ledger(description, disbursement.reference, entries, posting_date=disbursement.created_at.date())
                disbursement.posted_to_gl = True

            # 3. Finalize Disbursement Flags
            disbursement.accounting_error = None
            disbursement.save(
                update_fields=["balance_updated", "posted_to_gl", "accounting_error"]
            )
            return True

    except Exception as e:
        error_msg = str(e)
        logger.critical(
            f"DISBURSEMENT GL FAILURE {disbursement.reference}: {error_msg}"
        )
        # Use update() to bypass transaction rollback for error logging
        type(disbursement).objects.filter(id=disbursement.id).update(
            accounting_error=f"Error at {now()}: {error_msg}"
        )
        raise e
