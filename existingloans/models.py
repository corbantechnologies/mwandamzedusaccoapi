from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from existingloans.utils import generate_existing_loan_account_number
from paymentaccounts.models import PaymentAccount
from glaccounts.models import GLAccount

User = get_user_model()


class ExistingLoan(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """
    This model is used to store the existing loans of the members of the sacco.
    This is a temporary bypass during system adoption.
    After a member's loan is fully repaid, this record will be deactivated.
    They will then be able to take new loans by following the normal loan application process.
    The GL Accounts are similar to the ones in the Loan model.
    The outstanding balance at the point of adoption becomes the principal balance of the loan.
    """

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Closed", "Closed"),
        ("Defaulted", "Defaulted"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="existing_loans"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_existing_loan_account_number
    )
    payment_method = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        related_name="existing_loans_payments",
        blank=True,
        null=True,
    )
    principal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text="The outstanding balance at the point of adoption. It is assumed that the interest and processing fee have been included in this amount.",
    )
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    total_interest_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="The total interest paid on the loan. Added manually during payment",
    )
    total_amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_penalties_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="The total penalties paid on the loan. Added manually during payment",
    )
    status = models.CharField(choices=STATUS_CHOICES, default="Active", max_length=20)
    posted_to_gl = models.BooleanField(default=False, editable=False)
    balance_updated = models.BooleanField(default=False, editable=False)
    accounting_error = models.TextField(blank=True, null=True)
    # GL Books
    # ASSET: Tracks the Principal raw amount lent out
    gl_principal_asset = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="existing_loans_principal_assets",
        null=True,
        blank=True,
    )
    # REVENUE: Tracks the actual profit recognized today
    gl_interest_revenue = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="existing_loans_interest_income",
        null=True,
        blank=True,
    )
    # REVENUE/INCOME: Tracks penalties
    gl_penalty_revenue = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        related_name="existing_loans_penalty_income",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Existing Loan"
        verbose_name_plural = "Existing Loans"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.outstanding_balance = self.principal - self.total_amount_paid
        if self.outstanding_balance <= 0:
            self.status = "Closed"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member} - {self.account_number} - {self.reference}"
