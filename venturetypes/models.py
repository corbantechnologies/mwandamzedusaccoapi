from django.db import models

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel
from glaccounts.models import GLAccount


class VentureType(UniversalIdModel, TimeStampedModel, ReferenceModel):
    """
    Represents the products that members can purchase on credit from the sacco.
    For example, solar panels, livestock, farm inputs, phones, etc.
    Each venture type has a specific interest rate and a specific GL account for loans.

    Questions:
    - How many GL accounts will each venture type have?
    - If I purchase a phone from the sacco, will the loan be recorded in a single GL account or multiple GL accounts?
    """

    name = models.CharField(max_length=255, unique=True)
    interest_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    gl_account = models.ForeignKey(
        GLAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="venture_types",
    )

    class Meta:
        verbose_name = "Venture Type"
        verbose_name_plural = "Venture Types"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
