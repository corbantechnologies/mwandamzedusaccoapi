from django.db import models

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel


class PostingLog(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """
    Log of all posting transactions.

    The postings are automatic so we need to keep a log of all posting transactions.
    """

    record = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Posting Log"
        verbose_name_plural = "Posting Logs"
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference
