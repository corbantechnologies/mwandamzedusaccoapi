from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
from journalbatches.models import JournalBatch
from glaccounts.models import GLAccount
from journalentries.utils import generate_journal_entry_code

User = get_user_model()


class JournalEntry(TimeStampedModel, UniversalIdModel, ReferenceModel):
    """A single side of a financial event."""

    batch = models.ForeignKey(
        JournalBatch, on_delete=models.CASCADE, related_name="entries"
    )
    account = models.ForeignKey(
        GLAccount, on_delete=models.PROTECT, related_name="entries"
    )
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0.0)
    code = models.CharField(
        max_length=20, unique=True, default=generate_journal_entry_code, editable=False
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_journal_entries",
    )

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.batch.code} - {self.account.code} ({self.debit or self.credit})"

    def save(self, *args, **kwargs):
        # Ensure only one of debit or credit is set
        if self.debit and self.credit:
            raise ValueError("An entry cannot be both debit and credit.")
        if not self.debit and not self.credit:
            raise ValueError("An entry must be either debit or credit.")

        # Update the account balance based on category
        # Assets/Expenses: DR+, CR-
        # Liabilities/Equity/Revenues: CR+, DR-
        if self.account.category in ["ASSET", "EXPENSE"]:
            self.account.balance += self.debit - self.credit
        else:
            self.account.balance += self.credit - self.debit

        self.account.save(update_fields=["balance"])
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Revert the account balance on deletion
        if self.account.category in ["ASSET", "EXPENSE"]:
            self.account.balance -= self.debit - self.credit
        else:
            self.account.balance -= self.credit - self.debit

        self.account.save(update_fields=["balance"])
        super().delete(*args, **kwargs)
