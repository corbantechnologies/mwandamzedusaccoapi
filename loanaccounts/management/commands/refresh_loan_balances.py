from django.core.management.base import BaseCommand
from loanaccounts.models import LoanAccount
from django.db import transaction


class Command(BaseCommand):
    help = "Recalculates the total_loan_amount and outstanding_balance for all LoanAccounts to include processing fees."

    def handle(self, *args, **options):
        loans = LoanAccount.objects.all()
        count = loans.count()
        self.stdout.write(f"Refreshing balances for {count} loan accounts...")

        updated_count = 0
        with transaction.atomic():
            for loan in loans:
                try:
                    # Calling save() triggers the updated model logic:
                    # total_loan_amount = principal + interest + processing_fee
                    loan.save()
                    updated_count += 1
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Failed to update loan {loan.account_number}: {str(e)}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully refreshed {updated_count}/{count} loan accounts."
            )
        )
