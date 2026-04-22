from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel
from loanaccounts.models import LoanAccount
from loanpenalties.utils import generate_penalty_code
from mwandamzedusaccoapi.settings import LOAN_PENALTY_RATE

User = get_user_model()


class LoanPenalty(UniversalIdModel, TimeStampedModel, ReferenceModel):
    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.CASCADE, related_name="penalties"
    )
    installment_code = models.CharField(max_length=50)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=f"Original penalty amount ({LOAN_PENALTY_RATE}% of the total installment due)",
        blank=True,
        null=True,
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cumulative amount paid toward this penalty. Updated by the payment service.",
    )
    status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Paid", "Paid"), ("Waived", "Waived")],
        default="Pending",
    )
    charged_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="penalties_charged"
    )
    penalty_code = models.CharField(
        max_length=50, unique=True, default=generate_penalty_code, editable=False
    )

    class Meta:
        verbose_name = "Loan Penalty"
        verbose_name_plural = "Loan Penalties"
        ordering = ["-created_at"]

    @property
    def balance(self):
        """Outstanding penalty amount yet to be paid."""
        from decimal import Decimal

        original = Decimal(str(self.amount or 0))
        paid = Decimal(str(self.amount_paid or 0))
        return max(Decimal("0"), original - paid)

    def __str__(self):
        return f"Penalty {self.penalty_code} on {self.loan_account.account_number} - {self.installment_code} for member {self.loan_account.member.member_no}"
