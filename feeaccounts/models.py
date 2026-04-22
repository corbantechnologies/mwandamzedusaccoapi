from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from feetypes.models import FeeType
from feeaccounts.utils import generate_fee_account_number

User = get_user_model()


class FeeAccount(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    - Created automatically after a fee type has been created;
    - Unless it is created for the member by the admin.
    """

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="fee_accounts"
    )
    fee_type = models.ForeignKey(
        FeeType, on_delete=models.CASCADE, related_name="fee_accounts"
    )
    account_number = models.CharField(
        max_length=20, unique=True, default=generate_fee_account_number
    )
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_balance = models.DecimalField(max_digits=15, decimal_places=2)
    is_paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Fee Account"
        verbose_name_plural = "Fee Accounts"
        ordering = ["-created_at"]

    def __str__(self):
        return self.account_number

    def save(self, *args, **kwargs):
        if self.outstanding_balance is None:
            self.outstanding_balance = self.fee_type.amount

        if self.outstanding_balance <= 0:
            self.is_paid = True
        else:
            self.is_paid = False
        super().save(*args, **kwargs)
