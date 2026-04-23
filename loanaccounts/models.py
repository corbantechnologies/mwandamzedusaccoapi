from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loanproducts.models import LoanProduct
from loanaccounts.utils import generate_loan_account_number
from loanapplications.models import LoanApplication

User = get_user_model()


class LoanAccount(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - Created automatically after a loan application has been approved;
    - Unless it is created for the member by the admin.
    """

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Funded", "Funded"),
        ("Closed", "Closed"),
        ("Defaulted", "Defaulted"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="loan_accounts"
    )
    application = models.OneToOneField(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name="loan_account",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        LoanProduct, on_delete=models.CASCADE, related_name="loans"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_loan_account_number
    )
    principal = models.DecimalField(max_digits=15, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    total_loan_amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    last_interest_calulation = models.DateField(null=True, blank=True)
    status = models.CharField(choices=STATUS_CHOICES, default="Active", max_length=20)
    total_interest_accrued = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    total_principal_paid = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    total_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    projection_snapshot = models.JSONField(default=dict, null=True, blank=True)
    processing_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Loan Account"
        verbose_name_plural = "Loan Accounts"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now().date()

        self.total_loan_amount = (
            self.principal
            + Decimal(str(self.total_interest_accrued))
            + Decimal(str(self.processing_fee))
        )
        self.outstanding_balance = self.total_loan_amount - self.total_amount_paid

        # Status Automation: Close if paid, set Active if funded
        if self.outstanding_balance <= 0:
            self.status = "Closed"
        elif self.status == "Funded":
            self.status = "Active"

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.member} - {self.product} - {self.account_number} - {self.reference}"
        )

    @property
    def total_penalties_owed(self):
        """Sum of outstanding balances across all Pending penalties on this account."""
        from decimal import Decimal

        total = Decimal("0")
        for pen in self.penalties.filter(status="Pending"):
            original = Decimal(str(pen.amount or 0))
            paid = Decimal(str(pen.amount_paid or 0))
            total += max(Decimal("0"), original - paid)
        return total

    @property
    def total_clearance_amount(self):
        """
        Estimated total amount required to fully close this loan today.
        = outstanding_balance + total_penalties_owed

        Note: For Flat Rate loans this is exact. For Reducing Balance loans
        this is an upper-bound estimate (outstanding_balance includes future
        interest that would be waived on early settlement). The exact figure
        is validated by the service at payment time.
        """
        from decimal import Decimal

        return Decimal(str(self.outstanding_balance)) + self.total_penalties_owed
