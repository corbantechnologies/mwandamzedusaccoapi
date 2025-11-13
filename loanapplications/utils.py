# loanapplications/utils.py
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

    # Only count self-guarantees from *active* loans
    committed_self = LoanApplication.objects.filter(
        member=application.member,
        loan_account__status__in=["Active", "Funded"],
        self_guaranteed_amount__gt=0,
    ).aggregate(t=models.Sum("self_guaranteed_amount"))["t"] or Decimal("0")

    available_self = max(Decimal("0"), total_savings - committed_self)

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
        "committed_self_guarantee": committed_self,
        "available_self_guarantee": available_self,
        "total_guaranteed_by_others": total_guaranteed_by_others,
        "effective_coverage": effective_coverage,
        "remaining_to_cover": remaining_to_cover,
        "is_fully_covered": is_fully_covered,
    }
