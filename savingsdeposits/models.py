from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import transaction
from datetime import date

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savings.models import SavingsAccount
from savingsdeposits.utils import generate_identity

User = get_user_model()


class SavingsDeposit(TimeStampedModel, UniversalIdModel, ReferenceModel):
    PAYMENT_METHOD_CHOICES = [
        ("Mpesa", "Mpesa"),
        ("Mpesa STK Push", "Mpesa STK Push"),
        ("Bank Transfer", "Bank Transfer"),
        ("Cash", "Cash"),
        ("Cheque", "Cheque"),
        ("Mobile Banking", "Mobile Banking"),
        ("Standing Order", "Standing Order"),
    ]
    DEPOSIT_TYPE_CHOICES = [
        ("Opening Balance", "Opening Balance"),
        ("Payroll Deduction", "Payroll Deduction"),
        ("Individual Deposit", "Individual Deposit"),
        ("Dividend Deposit", "Dividend Deposit"),
        ("Other", "Other"),
    ]
    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]
    MPESA_PAYMENT_STATUS_CHOICES = (
        ("PENDING", "PENDING"),
        ("COMPLETED", "COMPLETED"),
        ("CANCELLED", "CANCELLED"),
        ("FAILED", "FAILED"),
        ("REVERSED", "REVERSED"),
    )

    savings_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="deposits",
    )
    deposited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="savings_deposits",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, default="KES")
    payment_method = models.CharField(
        max_length=100, choices=PAYMENT_METHOD_CHOICES, default="Cash"
    )
    deposit_type = models.CharField(
        max_length=100, choices=DEPOSIT_TYPE_CHOICES, default="Individual Deposit"
    )
    transaction_status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS_CHOICES, default="Pending"
    )
    is_active = models.BooleanField(default=True)
    receipt_number = models.CharField(max_length=50, blank=True, null=True)
    identity = models.CharField(
        max_length=100, unique=True, default=generate_identity, editable=False
    )

    # Mpesa fields:
    checkout_request_id = models.CharField(max_length=2550, blank=True, null=True)
    callback_url = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=MPESA_PAYMENT_STATUS_CHOICES, default="PENDING"
    )
    payment_status_description = models.CharField(max_length=100, blank=True, null=True)
    confirmation_code = models.CharField(max_length=100, blank=True, null=True)
    payment_account = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=2550, blank=True, null=True)
    mpesa_phone_number = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Savings Deposit"
        verbose_name_plural = "Savings Deposits"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["savings_account", "created_at"]),
            models.Index(fields=["deposited_by", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Deposit {self.reference} - {self.amount} to {self.savings_account}"
