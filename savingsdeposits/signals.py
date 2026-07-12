from django.db.models.signals import post_save
from django.dispatch import receiver
from savingsdeposits.models import SavingsDeposit
from journalbatches.models import JournalBatch

@receiver(post_save, sender=SavingsDeposit)
def sync_deposit_transaction_date_to_gl(sender, instance, created, **kwargs):
    """
    Ensures that any update to a SavingsDeposit's transaction_date 
    is perfectly mirrored in its associated JournalBatch posting_date.
    """
    if not created and instance.reference:
        batch = JournalBatch.objects.filter(reference=instance.reference).first()
        if batch and batch.posting_date != instance.transaction_date:
            batch.posting_date = instance.transaction_date
            batch.save(update_fields=['posting_date'])
