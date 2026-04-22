import logging
from django.db import transaction
from django.utils.timezone import now
from financials.services import post_to_ledger

logger = logging.getLogger(__name__)


def process_fee_payment_accounting(payment):
    """
    Atomic service for Fee Payment:
    1. Increases the SACCO Bank (Asset).
    2. Recognizes Fee Income (Revenue).
    3. Updates the member's FeeAccount operational balance.
    """
    if payment.transaction_status != "Completed":
        return False

    if payment.posted_to_gl and payment.balance_updated:
        return True

    fee_acc = payment.fee_account
    fee_type = fee_acc.fee_type

    try:
        with transaction.atomic():
            # 1. Update Operational State
            if not payment.balance_updated:
                fee_acc.amount_paid += payment.amount
                fee_acc.outstanding_balance -= payment.amount
                if fee_acc.outstanding_balance <= 0:
                    fee_acc.is_paid = True
                fee_acc.save(
                    update_fields=["amount_paid", "outstanding_balance", "is_paid"]
                )
                payment.balance_updated = True

            # 2. Post to General Ledger
            if not payment.posted_to_gl:
                if not payment.payment_method or not payment.payment_method.gl_account:
                    raise ValueError(
                        f"No GL Account linked to Payment Method: {payment.payment_method}"
                    )

                bank_gl = payment.payment_method.gl_account
                revenue_gl = (
                    fee_type.gl_account
                )  # Fee types map directly to Revenue accounts

                if not revenue_gl:
                    raise ValueError(
                        f"No GL Account linked to Fee Type: {fee_type.name}"
                    )

                description = (
                    f"Fee Payment: {fee_type.name} | Member: {fee_acc.member.member_no}"
                )

                entries = [
                    # BANK: Increase Cash (Debit increases Asset)
                    {"account": bank_gl, "debit": payment.amount, "credit": 0},
                    # REVENUE: Recognize Income (Credit increases Revenue)
                    {"account": revenue_gl, "debit": 0, "credit": payment.amount},
                ]

                # post_to_ledger handles the zero-check globally
                post_to_ledger(description, payment.reference, entries, posting_date=payment.created_at.date())
                payment.posted_to_gl = True

            # 3. Finalize
            payment.accounting_error = None
            payment.save(
                update_fields=["balance_updated", "posted_to_gl", "accounting_error"]
            )
            return True

    except Exception as e:
        error_msg = str(e)
        logger.critical(f"FEE PAYMENT GL FAILURE {payment.reference}: {error_msg}")
        # Persist error independent of rollback
        type(payment).objects.filter(id=payment.id).update(
            accounting_error=f"Error at {now()}: {error_msg}"
        )
        raise e
