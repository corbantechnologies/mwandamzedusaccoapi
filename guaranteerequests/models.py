from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.abstracts import ReferenceModel, UniversalIdModel, TimeStampedModel
from loanapplications.models import LoanApplication
from guarantors.models import GuarantorProfile

User = get_user_model()


class GuaranteeRequest(UniversalIdModel, TimeStampedModel, ReferenceModel):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("Declined", "Declined"),
        ("Cancelled", "Cancelled"),
    ]

    member = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="guarantor_requests"
    )
    loan_application = models.ForeignKey(
        LoanApplication, on_delete=models.CASCADE, related_name="guarantee_requests"
    )
    guarantor = models.ForeignKey(
        GuarantorProfile, on_delete=models.CASCADE, related_name="guarantees"
    )
    guaranteed_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Pending")

    class Meta:
        verbose_name = "Guarantee Request"
        verbose_name_plural = "Guarantee Requests"
        unique_together = ("loan_application", "guarantor")
        ordering = ["-created_at"]

    def clean(self):
        if self.guaranteed_amount <= 0:
            raise ValidationError("Amount must be > 0")

        if not self.guarantor.is_eligible:
            raise ValidationError(f"{self.guarantor} is not eligible to guarantee")

        current = self.guarantor.committed_amount()
        if self.member_no:
            old = GuaranteeRequest.objects.get(
                member_no=self.member_no
            ).guaranteed_amount
            current -= old
        if current + self.guaranteed_amount > self.guarantor.max_guarantee_amount:
            raise ValidationError(f"{self.guarantor} exceeds max guarantee amount")

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member_no} - {self.guaranteed_amount}"
