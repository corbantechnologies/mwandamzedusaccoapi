from django.db import models
from django.contrib.auth import get_user_model
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loanproducts.models import LoanProduct

User = get_user_model()


class LoanApplication(UniversalIdModel, TimeStampedModel, ReferenceModel):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Ready for Amendment", "Ready for Amendment"),
        ("Amended", "Amended"),
        ("In Progress", "In Progress"),
        ("Ready for Submission", "Ready for Submission"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Disbursed", "Disbursed"),
        ("Declined", "Declined"),
        ("Cancelled", "Cancelled"),
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
    term_months = models.PositiveIntegerField()
    repayment_frequency = models.CharField(
        max_length=40, choices=REPAYMENT_FREQUENCY_CHOICES, default="monthly"
    )
    start_date = models.DateField(
        default=date.today, help_text="Loan disbursement date (used for projection)"
    )
    repayment_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    total_interest = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    self_guaranteed_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    projection_snapshot = models.JSONField(
        null=True, blank=True, help_text="Full repayment projection"
    )
    amendment_note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Loan Application"
        verbose_name_plural = "Loan Applications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member} - {self.product.name} - {self.requested_amount}"
