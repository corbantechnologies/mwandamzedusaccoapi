from django.core.management.base import BaseCommand
from loanapplications.models import LoanApplication
from loanaccounts.models import LoanAccount
from django.db import transaction


class Command(BaseCommand):
    help = "Updates existing projection snapshots to include is_paid field"

    def handle(self, *args, **options):
        self.stdout.write("Updating LoanApplication projections...")
        self.update_projections(LoanApplication)

        self.stdout.write("Updating LoanAccount projections...")
        self.update_projections(LoanAccount)

        self.stdout.write(self.style.SUCCESS("Successfully updated all projections"))

    def update_projections(self, model):
        items = model.objects.filter(projection_snapshot__isnull=False)
        updated_count = 0

        with transaction.atomic():
            for item in items:
                snapshot = item.projection_snapshot
                if not snapshot or "schedule" not in snapshot:
                    continue

                modified = False
                for entry in snapshot["schedule"]:
                    if "is_paid" not in entry:
                        entry["is_paid"] = False
                        modified = True

                if modified:
                    # JSONField in Django needs a fresh assignment for it to detect changes
                    # especially when modifying nested keys
                    item.projection_snapshot = snapshot
                    item.save(update_fields=["projection_snapshot"])
                    updated_count += 1

        self.stdout.write(f"Updated {updated_count} {model.__name__} records")
