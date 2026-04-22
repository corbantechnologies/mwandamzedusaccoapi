from django.db import models
from django.utils import timezone

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from journalbatches.utils import generate_journal_batch_code


class JournalBatch(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """Links the two or more sides of a single financial event."""

    description = models.CharField(max_length=5000)
    code = models.CharField(
        max_length=20, unique=True, default=generate_journal_batch_code, editable=False
    )
    posted = models.BooleanField(default=False)
    posting_date = models.DateField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Journal Batch"
        verbose_name_plural = "Journal Batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.description}"
