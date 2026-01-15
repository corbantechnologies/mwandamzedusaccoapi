from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from loandisbursements.utils import generate_loan_disbursement_code
from loanaccounts.models import LoanAccount

User = get_user_model()


class LoanDisbursement(UniversalIdModel, TimeStampedModel, ReferenceModel):
    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
        ("Failed", "Failed"),
    ]

    DISBURSEMENT_TYPE_CHOICES = [
        ("Principal", "Principal"),
        ("Interest", "Interest"),
        ("Penalty", "Penalty"),
        ("Refill", "Refill"),
    ]
    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.PROTECT, related_name="disbursements"
    )
    disbursed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    currency = models.CharField(max_length=3, default="KES")
    transaction_status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS_CHOICES, default="Pending"
    )
    disbursement_type = models.CharField(
        max_length=20, choices=DISBURSEMENT_TYPE_CHOICES, default="Principal"
    )
    transaction_code = models.CharField(
        max_length=46,
        unique=True,
        default=generate_loan_disbursement_code,
        editable=False,
    )
    # MPESA Details
    # TODO: to be implemented

    class Meta:
        verbose_name = "Loan Disbursement"
        verbose_name_plural = "Loan Disbursements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.loan_account} - {self.disbursement_type} - {self.amount}"

    def save(self, *args, **kwargs):
        if (
            self.transaction_status == "Completed"
            and self.disbursement_type == "Principal"
        ):
            self.loan_account.status = "Funded"
            self.loan_account.save(update_fields=["status"])
        super().save(*args, **kwargs)
