from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from mwandamzeduapi.settings import MAX_GUARANTEES
from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savings.models import SavingsAccount

User = get_user_model()


class GuarantorProfile(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    Created by SACCO Admin
    Only eligible members can guarntee
    """

    member = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="guarantor_profile"
    )
    is_eligible = models.BooleanField(default=False)
    eligibility_checked_at = models.DateTimeField(null=True, blank=True)
    max_active_guarantees = models.PositiveIntegerField(default=MAX_GUARANTEES)
    max_guarantee_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )

    class Meta:
        verbose_name = "Guarantor Profile"
        verbose_name_plural = "Guarantor Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.member_no} – Eligible: {self.is_eligible}"

    def save(self, *args, **kwargs):
        if self.is_eligible and not self.eligibility_checked_at:
            self.eligibility_checked_at = timezone.now()

        if self.reference:
            total_savings = SavingsAccount.objects.filter(member=self.member).aggregate(
                total=models.Sum("balance")
            )["total"] or Decimal("0")
            self.max_guarantee_amount = total_savings

        super().save(*args, **kwargs)

    def committed_amount(self):
        """Dynamic: sum of Accepted guarantees"""
        total = self.guarantees.filter(status="Accepted").aggregate(
            total=models.Sum("guaranteed_amount")
        )["total"]
        return total or Decimal("0")
