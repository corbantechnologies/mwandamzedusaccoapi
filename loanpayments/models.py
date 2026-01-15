from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import ReferenceModel, UniversalIdModel, TimeStampedModel
from loanaccounts.models import LoanAccount
from loanpayments.utils import generate_loan_payment_code

User = get_user_model()


class LoanPayment(ReferenceModel, UniversalIdModel, TimeStampedModel):
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
        ("Mobile Banking", "Mobile Banking"),
        ("Standing Order", "Standing Order"),
    ]

    REPAYMENT_TYPE_CHOICES = [
        ("Regular Repayment", "Regular Repayment"),
        ("Standing Order", "Standing Order"),
        ("Interest Payment", "Interest Payment"),
        ("Individual Settlement", "Individual Settlement"),
        ("Early Settlement", "Early Settlement"),
        ("Partial Payment", "Partial Payment"),
    ]

    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    loan_account = models.ForeignKey(
        LoanAccount, on_delete=models.PROTECT, related_name="loan_payments"
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_payments",
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default="Mpesa"
    )
    repayment_type = models.CharField(
        max_length=20, choices=REPAYMENT_TYPE_CHOICES, default="Regular Repayment"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS_CHOICES, default="Pending"
    )
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_code = models.CharField(
        max_length=76, unique=True, default=generate_loan_payment_code, editable=False
    )

    # TODO: Add Mpesa Transaction Details

    class Meta:
        verbose_name = "Loan Payment"
        verbose_name_plural = "Loan Payments"
        ordering = ["-payment_date"]

    
