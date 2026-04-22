from django.db import models

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel


class MpesaBody(UniversalIdModel, TimeStampedModel, ReferenceModel):
    body = models.JSONField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "M-Pesa Body"
        verbose_name_plural = "M-Pesa Bodies"

    def __str__(self):
        return self.reference
