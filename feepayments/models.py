from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

from accounts.abstracts import ReferenceModel, TimeStampedModel, UniversalIdModel
from paymentaccounts.models import PaymentAccount
from feeaccounts.models import FeeAccount
from feepayments.utils import generate_fee_payment_code
from mpesa.abstracts import MpesaPaymentModel

User = get_user_model()


class FeePayment(TimeStampedModel, UniversalIdModel, ReferenceModel, MpesaPaymentModel):

    TRANSACTION_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]
    fee_account = models.ForeignKey(
        FeeAccount, on_delete=models.PROTECT, related_name="fee_payments"
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="fee_payments",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01, message="Amount must be greater than 0")],
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    currency = models.CharField(max_length=10, default="KES")
    payment_method = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        related_name="fee_payments",
    )
    code = models.CharField(
        max_length=100, unique=True, default=generate_fee_payment_code, editable=False
    )
    transaction_status = models.CharField(
        max_length=100, choices=TRANSACTION_STATUS_CHOICES, default="Pending"
    )
    posted_to_gl = models.BooleanField(default=False, editable=False)
    balance_updated = models.BooleanField(default=False, editable=False)
    accounting_error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Fee Payment"
        verbose_name_plural = "Fee Payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["fee_account", "created_at"]),
            models.Index(fields=["paid_by", "created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"Fee Payment {self.reference} - {self.amount} to {self.fee_account}"
