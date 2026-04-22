from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import ReferenceModel, UniversalIdModel, TimeStampedModel
from loanaccounts.models import LoanAccount
from loanpayments.utils import generate_loan_payment_code
from paymentaccounts.models import PaymentAccount
from mpesa.abstracts import MpesaPaymentModel

User = get_user_model()


class LoanPayment(
    ReferenceModel, UniversalIdModel, TimeStampedModel, MpesaPaymentModel
):

    REPAYMENT_TYPE_CHOICES = [
        ("Regular Repayment", "Regular Repayment"),
        ("Partial Payment", "Partial Payment"),
        ("Early Settlement", "Early Settlement"),
        (
            "Penalty Payment",
            "Penalty Payment",
        ),  # Specifically for the penalty charges
        (
            "Loan Clearance",
            "Loan Clearance",
        ),  # Early Settlement + all pending penalties in one transaction
        ("Interest Only", "Interest Only"),
        # this is for the mpesa payments made by members. Does not affect the loan account balance
        ("Mpesa STK Push", "Mpesa STK Push"),
    ]

    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.PROTECT, related_name="loan_payments"
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_payments",
    )
    payment_method = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        related_name="loan_payments",
        null=True,
        blank=True,
    )
    repayment_type = models.CharField(
        max_length=70, choices=REPAYMENT_TYPE_CHOICES, default="Regular Repayment"
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
        max_length=76, unique=True, default=generate_loan_payment_code, editable=False
    )
    posted_to_gl = models.BooleanField(default=False, editable=False)
    balance_updated = models.BooleanField(default=False, editable=False)
    accounting_error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Loan Payment"
        verbose_name_plural = "Loan Payments"
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["loan_account", "payment_date"]),
            models.Index(fields=["paid_by", "payment_date"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Payment {self.reference} - {self.amount} to {self.loan_account}"
