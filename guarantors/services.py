from decimal import Decimal
from django.db import transaction
from django.db.models import F


@transaction.atomic
def sync_guarantor_profile(profile):
    """
    Recalculates and saves the committed guarantee amount for a profile.
    """
    from guarantors.models import GuarantorProfile

    profile.recalculate_committed_amount()
    profile.save(update_fields=["committed_guarantee_amount", "max_guarantee_amount"])
    return profile


@transaction.atomic
def release_guarantees_for_application(loan_app):
    """
    Releases all accepted guarantees for a loan application.
    Updates the committed amounts for all affected guarantors.
    """
    # 1. Reset self_guaranteed_amount on the application
    if loan_app.self_guaranteed_amount > 0:
        loan_app.self_guaranteed_amount = Decimal("0")
        loan_app.save(update_fields=["self_guaranteed_amount"])

    # 2. Update all accepted guarantee records to 'Cancelled'
    # and collect the profiles to sync
    guarantees = loan_app.guarantors.filter(status="Accepted")
    profiles_to_sync = set()

    for g in guarantees:
        profiles_to_sync.add(g.guarantor)
        g.status = "Cancelled"
        g.save(update_fields=["status"])

    # 3. Always include the application member's profile if it exists
    try:
        profiles_to_sync.add(loan_app.member.guarantor_profile)
    except:
        pass

    # 4. Perform the sync for all affected profiles
    for profile in profiles_to_sync:
        sync_guarantor_profile(profile)


def update_guarantee_status(guarantee_request, new_status, amount=None):
    """
    Updates the status of a guarantee request and syncs the guarantor profile.
    """
    with transaction.atomic():
        if amount is not None:
            guarantee_request.guaranteed_amount = amount

        guarantee_request.status = new_status
        guarantee_request.save(update_fields=["status", "guaranteed_amount"])

        sync_guarantor_profile(guarantee_request.guarantor)

        # If it's a self-guarantee, update the loan application field too
        if guarantee_request.guarantor.member == guarantee_request.member:
            loan = guarantee_request.loan_application
            if new_status == "Accepted":
                loan.self_guaranteed_amount = guarantee_request.guaranteed_amount
            else:
                loan.self_guaranteed_amount = Decimal("0")
            loan.save(update_fields=["self_guaranteed_amount"])

    return guarantee_request


def update_guarantees_on_repayment(loan_account, principal_reduction):
    """
    Reduces the guaranteed_amount of all Accepted guarantees for a loan
    proportionally based on the principal reduction.
    Also updates the self_guaranteed_amount on the loan application.
    """
    if principal_reduction <= 0:
        return

    loan_app = loan_account.application
    if not loan_app:
        return

    # 1. Get all active guarantees and separate owner from others
    # to avoid doubling (owner is in both the relation and self_guaranteed_amount)
    all_accepted_guarantees = loan_app.guarantors.filter(status="Accepted")
    external_guarantees = all_accepted_guarantees.exclude(
        guarantor__member=loan_app.member
    )
    self_guarantee_amt = loan_app.self_guaranteed_amount

    # 2. Total currently guaranteed (sum of external + owner's committed amount)
    total_guaranteed = (
        sum(g.guaranteed_amount for g in external_guarantees) + self_guarantee_amt
    )

    if total_guaranteed <= 0:
        return

    # 3. Calculate reduction factor and apply proportionally
    with transaction.atomic():
        # Update external guarantees
        for g in external_guarantees:
            reduction = (g.guaranteed_amount / total_guaranteed) * principal_reduction
            g.guaranteed_amount = max(Decimal("0"), g.guaranteed_amount - reduction)
            g.save(update_fields=["guaranteed_amount"])
            sync_guarantor_profile(g.guarantor)

        # Update self guarantee and keep the owner's GuaranteeRequest in sync
        if self_guarantee_amt > 0:
            reduction = (self_guarantee_amt / total_guaranteed) * principal_reduction
            new_self_amt = max(Decimal("0"), self_guarantee_amt - reduction)

            # Update the summary field on the application
            loan_app.self_guaranteed_amount = new_self_amt
            loan_app.save(update_fields=["self_guaranteed_amount"])

            # Update the owner's specific GuaranteeRequest record if it exists
            all_accepted_guarantees.filter(guarantor__member=loan_app.member).update(
                guaranteed_amount=new_self_amt
            )

            # Sync member's profile for self-guarantee
            try:
                sync_guarantor_profile(loan_app.member.guarantor_profile)
            except:
                pass
