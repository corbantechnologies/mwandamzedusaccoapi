from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from savings.models import SavingsAccount

User = get_user_model()


class GuarantorProfile(UniversalIdModel, TimeStampedModel, ReferenceModel):
    member = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="guarantor_profile"
    )
    is_eligible = models.BooleanField(default=False)
    eligibility_checked_at = models.DateTimeField(null=True, blank=True)
    max_active_guarantees = models.PositiveIntegerField(
        default=3, help_text="Max number of loans this member can guarantee"
    )
    max_guarantee_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )
    committed_guarantee_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0
    )

    class Meta:
        verbose_name = "Guarantor Profile"
        verbose_name_plural = "Guarantor Profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.member_no} – Eligible: {self.is_eligible}"

    def recalculate_committed_amount(self):
        """
        Recalculates committed_guarantee_amount based on ALL accepted guarantee records
        for loans that are NOT in a final released state (Disbursed is tricky, usually locks until paid).
        Actually, for simplicity and accuracy, we sum all 'Accepted' guarantees for loans that are:
        - Submitted, Approved, Disbursed, (and In Progress/Pending if they lock early).
        For now, let's include everything except Declined/Cancelled.
        """
        from guaranteerequests.models import GuaranteeRequest
        from django.db.models import Sum

        # Loans that should lock funds
        active_statuses = [
            "Pending",
            "Ready for Amendment",
            "Amended",
            "In Progress",
            "Ready for Submission",
            "Submitted",
            "Approved",
            "Disbursed",
        ]

        total = GuaranteeRequest.objects.filter(
            guarantor=self,
            status="Accepted",
            loan_application__status__in=active_statuses,
        ).aggregate(total=Sum("guaranteed_amount"))["total"] or Decimal("0")

        self.committed_guarantee_amount = total
        return total

    def save(self, *args, **kwargs):
        # Always sync max_guarantee_amount with current savings
        if self.pk:  # Only for existing instances
            total_savings = SavingsAccount.objects.filter(
                member=self.member, account_type__can_guarantee=True
            ).aggregate(total=models.Sum("balance"))["total"] or Decimal("0")
            self.max_guarantee_amount = total_savings

        if self.is_eligible and not self.eligibility_checked_at:
            self.eligibility_checked_at = timezone.now()

        super().save(*args, **kwargs)

    def available_capacity(self):
        return max(
            Decimal("0"), self.max_guarantee_amount - self.committed_guarantee_amount
        )

    def active_guarantees_count(self):
        from guaranteerequests.models import GuaranteeRequest

        return GuaranteeRequest.objects.filter(
            guarantor=self,
            status="Accepted",
            loan_application__status__in=["Submitted", "Approved", "Disbursed"],
        ).count()
