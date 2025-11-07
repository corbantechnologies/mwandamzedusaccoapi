from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.abstracts import ReferenceModel, UniversalIdModel, TimeStampedModel
from loanapplications.models import LoanApplication
from guarantors.models import GuarantorProfile

User = get_user_model()


class GuaranteeRequest(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    Guarantee Request:
    - Raised by the member requesting another member to guarantee
    - Checks if member is eligible:
        1. Potential Guarantor has an eligible guarantor profile
        2. Potential Guarantor has not exceeded the guarantor limit
    - If the member is eligible, a request is raised
    - Guarantor approves or declines the request thereby updating the status
    """

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
        LoanApplication, on_delete=models.CASCADE, related_name="guarantors"
    )
    guarantor = models.ForeignKey(
        GuarantorProfile, on_delete=models.CASCADE, related_name="guarantees"
    )
    guaranteed_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="Pending")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Guarantee Request"
        verbose_name_plural = "Guarantee Requests"
        unique_together = ("loan_application", "guarantor")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.member_no} - {self.guaranteed_amount}"
