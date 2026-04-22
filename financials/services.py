# financials/services.py
import logging
from datetime import date
from decimal import Decimal
from django.db import transaction
from journalentries.models import JournalEntry
from journalbatches.models import JournalBatch
from financials.models import PostingLog

logger = logging.getLogger(__name__)


def post_to_ledger(description, reference, entries, posting_date=None):
    """
    Post a journal entry to the ledger with a safety check for zero-value entries.
    """
    with transaction.atomic():
        # 1. Pre-filter zero entries to ensure validation logic doesn't fail
        active_entries = []
        for e in entries:
            dr = Decimal(str(e.get("debit", 0)))
            cr = Decimal(str(e.get("credit", 0)))
            if dr != 0 or cr != 0:
                active_entries.append(e)

        if not active_entries:
            logger.warning(
                f"No active movements for reference {reference}. Skipping GL."
            )
            return None

        # 2. Validation: Sum of Debits must equal Sum of Credits
        total_dr = sum(Decimal(str(e.get("debit", 0))) for e in active_entries)
        total_cr = sum(Decimal(str(e.get("credit", 0))) for e in active_entries)

        if total_dr != total_cr:
            raise ValueError(
                f"Accounting Error: Unbalanced entry. DR: {total_dr}, CR: {total_cr}"
            )

        # 3. Create Batch
        create_kwargs = {"description": description, "reference": reference}
        if posting_date:
            # Handle both date objects and strings if necessary, though date objects are preferred
            create_kwargs["posting_date"] = posting_date

        batch = JournalBatch.objects.create(**create_kwargs)

        # 4. Create Entries (Only for non-zero amounts)
        serializable_entries = []
        for entry in active_entries:
            acc = entry["account"]
            dr = Decimal(str(entry.get("debit", 0)))
            cr = Decimal(str(entry.get("credit", 0)))

            JournalEntry.objects.create(
                batch=batch,
                account=acc,
                debit=dr,
                credit=cr,
            )

            serializable_entries.append(
                {
                    "account": str(acc),
                    "debit": str(dr),
                    "credit": str(cr),
                }
            )

        # 5. Finalize Batch and Log
        batch.posted = True
        batch.save(update_fields=["posted"])

        posting_log = {
            "batch": batch.reference,
            "batch_code": batch.code,
            "batch_status": batch.posted,
            "posting_date": str(batch.posting_date),
            "description": description,
            "entries": serializable_entries,
        }
        PostingLog.objects.create(
            record=posting_log,
            reference=reference,
        )

        return batch
