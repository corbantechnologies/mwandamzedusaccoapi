from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import ReferenceModel, UniversalIdModel, TimeStampedModel
from mpesa.abstracts import MpesaPaymentModel
from existingloans.models import ExistingLoan
from paymentaccounts.models import PaymentAccount
from existingloanspayments.utils import generate_existing_loan_payment_code

User = get_user_model()


class ExistingLoanPayment(
    ReferenceModel, UniversalIdModel, TimeStampedModel, MpesaPaymentModel
):
    """
    Represents a payment made towards an existing loan.
    """

    REPAYMENT_TYPE_CHOICES = [
        ("Regular Repayment", "Regular Repayment"),
        ("Partial Payment", "Partial Payment"),
        ("Early Settlement", "Early Settlement"),
        ("Penalty Payment", "Penalty Payment"),
        ("Loan Clearance", "Loan Clearance"),
        ("Interest Only", "Interest Only"),
    ]

    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    existing_loan = models.ForeignKey(
        ExistingLoan, on_delete=models.PROTECT, related_name="payments"
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="existing_loan_payments",
    )
    payment_method = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        related_name="existing_loan_payments",
        null=True,
        blank=True,
    )
    repayment_type = models.CharField(
        max_length=70,
        choices=REPAYMENT_TYPE_CHOICES,
        default="Regular Repayment",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default="Pending",
        help_text="The main status of the transaction",
    )
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_code = models.CharField(
        max_length=76,
        unique=True,
        default=generate_existing_loan_payment_code,
        editable=False,
    )
    posted_to_gl = models.BooleanField(default=False, editable=False)
    balance_updated = models.BooleanField(default=False, editable=False)
    accounting_error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Existing Loan Payment"
        verbose_name_plural = "Existing Loan Payments"
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["existing_loan", "payment_date"]),
            models.Index(fields=["paid_by", "payment_date"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Payment {self.reference} - {self.amount} to {self.existing_loan}"
