from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loanapplications.models import LoanApplication


def compute_loan_coverage(application):
    """
    Returns accurate coverage using:
    - Available self-guarantee (savings - committed from active loans)
    - Accepted external guarantees
    """
    total_savings = SavingsAccount.objects.filter(member=application.member).aggregate(
        t=models.Sum("balance")
    )["t"] or Decimal("0")

    # Calculate available based on GuarantorProfile logic
    try:
        from guarantors.models import GuarantorProfile

        profile = GuarantorProfile.objects.get(member=application.member)
        # Sync max_guarantee just in case (optional, but good for accuracy)
        # profile.max_guarantee_amount = total_savings
        # profile.save()

        # Committed includes guarantees for others AND self-guarantees on other loans
        committed_total = profile.committed_guarantee_amount
    except GuarantorProfile.DoesNotExist:
        committed_total = Decimal("0")

    available_self = max(Decimal("0"), total_savings - committed_total)

    total_guaranteed_by_others = application.guarantors.filter(
        status="Accepted"
    ).aggregate(t=models.Sum("guaranteed_amount"))["t"] or Decimal("0")

    effective_coverage = available_self + total_guaranteed_by_others
    remaining_to_cover = max(
        Decimal("0"), application.requested_amount - effective_coverage
    )
    is_fully_covered = remaining_to_cover <= 0

    return {
        "total_savings": total_savings,
        "committed_self_guarantee": committed_total,
        "available_self_guarantee": available_self,
        "total_guaranteed_by_others": total_guaranteed_by_others,
        "effective_coverage": effective_coverage,
        "remaining_to_cover": remaining_to_cover,
        "is_fully_covered": is_fully_covered,
    }
