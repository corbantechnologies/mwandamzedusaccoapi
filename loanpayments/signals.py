from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from loanpayments.models import LoanPayment


@receiver(post_save, sender=LoanPayment)
def update_loan_outstanding_balance(sender, instance, created, **kwargs):
    if instance.transaction_status.lower() == "completed":
        loan_account = instance.loan_account

        # Aggregate all completed payments to ensure accuracy
        total_paid = (
            LoanPayment.objects.filter(
                loan_account=loan_account, transaction_status="Completed"
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        loan_account.total_amount_paid = total_paid
        # saving triggers the arithmetic for outstanding_balance
        loan_account.save()
