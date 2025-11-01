from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loanproducts.models import LoanProduct

User = get_user_model()


class LoanApplication(UniversalIdModel, TimeStampedModel, ReferenceModel):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("In Progress", "In Progress"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Disbursed", "Disbursed"),
        ("Declined", "Declined"),
    ]

    REPAYMENT_FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annually", "Annually"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="loan_applications"
    )
    product = models.ForeignKey(
        LoanProduct, on_delete=models.PROTECT, related_name="applications"
    )
    requested_amount = models.DecimalField(max_digits=15, decimal_places=2)
    term_months = models.PositiveIntegerField(null=True, blank=True)
    repayment_frequency = models.CharField(
        max_length=40,
        choices=REPAYMENT_FREQUENCY_CHOICES,
        default="monthly",
        help_text="How often borrower makes payments",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    projection_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Exact projection shown to borrower at application time",
    )
    # Add fields for guarantors or rather guarantor functionality

    class Meta:
        verbose_name = "Loan Application"
        verbose_name_plural = "Loan Applications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member} - {self.product.name} - {self.requested_amount}"
