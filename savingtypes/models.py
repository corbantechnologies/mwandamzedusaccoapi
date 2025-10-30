from django.db import models

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel


class SavingType(UniversalIdModel, TimeStampedModel, ReferenceModel):
    name = models.CharField(max_length=255, unique=True)
    interest_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Savings Account Type"
        verbose_name_plural = "Savings Account Types"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
