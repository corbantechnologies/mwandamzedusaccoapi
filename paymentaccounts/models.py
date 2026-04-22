from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import ReferenceModel, TimeStampedModel, UniversalIdModel
from paymentaccounts.utils import generate_payment_account_code
from glaccounts.models import GLAccount

User = get_user_model()


class PaymentAccount(ReferenceModel, TimeStampedModel, UniversalIdModel):
    """
    All the payment accounts that receive and disburse payments
    Where member make payments to the SACCO
    """

    name = models.CharField(
        max_length=1000,
        unique=True,
        help_text="I&M Bank, M-Pesa, etc. Just a short name for the member to reference",
    )
    code = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        default=generate_payment_account_code,
        help_text="Unique code for the payment account",
    )
    gl_account = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_accounts",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Payment Account"
        verbose_name_plural = "Payment Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
