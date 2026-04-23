import logging
from django.db import transaction
from django.utils.timezone import now
from savingsdeposits.models import SavingsDeposit
from financials.services import post_to_ledger

logger = logging.getLogger(__name__)


def process_savings_deposit_accounting(deposit):
    """
    Atomic service to update operational balance and post to GL.
    Designed to be idempotent (safe to call multiple times).
    """

    # 1. Safety Check: Only process 'Completed' operational transactions
    if deposit.transaction_status != "Completed":
        logger.warning(f"Deposit {deposit.reference} is not marked as Completed.")
        return False

    # 2. Idempotency Check: Don't re-process if already done
    if deposit.posted_to_gl and deposit.balance_updated:
        logger.info(f"Deposit {deposit.reference} has already been processed.")
        return True

    try:
        with transaction.atomic():
            # 3. Update Operational Balance
            if not deposit.balance_updated:
                account = deposit.savings_account
                # Use F() expressions for high-concurrency safety if needed,
                # but simple addition is fine within an atomic block.
                account.balance += deposit.amount
                account.save(update_fields=["balance"])
                deposit.balance_updated = True

            # 4. Post to General Ledger
            if not deposit.posted_to_gl:
                if not deposit.payment_method or not deposit.payment_method.gl_account:
                    raise ValueError(
                        f"No GL Account linked to Payment Method: {deposit.payment_method}"
                    )

                bank_gl = deposit.payment_method.gl_account
                savings_gl = deposit.savings_account.account_type.gl_account

                if not savings_gl:
                    raise ValueError(
                        f"No GL Account linked to Saving Type: {deposit.savings_account.account_type}"
                    )

                description = f"Savings Deposit: {deposit.savings_account.account_number} for member: {deposit.savings_account.member.member_no}"

                entries = [
                    {
                        "account": bank_gl,
                        "debit": deposit.amount,
                        "credit": 0,
                    },  # Increase Asset
                    {
                        "account": savings_gl,
                        "debit": 0,
                        "credit": deposit.amount,
                    },  # Increase Liability
                ]

                post_to_ledger(
                    description,
                    deposit.reference,
                    entries,
                    posting_date=deposit.created_at.date(),
                )
                deposit.posted_to_gl = True

            # 5. Finalize Flags and Clear previous errors on success
            deposit.accounting_error = None
            deposit.save(
                update_fields=["balance_updated", "posted_to_gl", "accounting_error"]
            )

            # 6. Affect Guarantor Profile if applicable
            if deposit.savings_account.account_type.can_guarantee:
                try:
                    from guarantors.models import GuarantorProfile
                    from guarantors.services import sync_guarantor_profile

                    profile, _ = GuarantorProfile.objects.get_or_create(
                        member=deposit.savings_account.member
                    )
                    sync_guarantor_profile(profile)
                except Exception as e:
                    logger.error(
                        f"Failed to sync guarantor profile for deposit {deposit.reference}: {e}"
                    )

            return True

    except Exception as e:
        error_msg = str(e)
        logger.critical(f"RECONCILIATION REQUIRED for {deposit.reference}: {error_msg}")

        # PERSIST ERROR: We use .update() because it executes a direct SQL command
        # that ignores the current 'atomic' rollback state of the transaction.
        SavingsDeposit.objects.filter(id=deposit.id).update(
            accounting_error=f"Error at {now()}: {error_msg}"
        )

        # Re-raise so the calling view knows the operation failed
        raise e
