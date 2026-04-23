from django.contrib import admin
from django.contrib import messages
from decimal import Decimal

from savingsdeposits.models import SavingsDeposit


@admin.register(SavingsDeposit)
class SavingsDepositAdmin(admin.ModelAdmin):
    list_display = (
        "savings_account",
        "deposited_by",
        "amount",
        "payment_method",
        "deposit_type",
        "transaction_status",
        "created_at",
    )
    list_filter = ("payment_method", "deposit_type", "transaction_status", "created_at")
    search_fields = (
        "savings_account__account_number",
        "deposited_by__member_no",
        "phone_number",
    )
    readonly_fields = ("created_at", "updated_at", "identity", "reference")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        """
        Override to update savings account balance when a new completed deposit is created
        via the admin interface.
        """
        # Save the object first (normal Django admin behavior)
        super().save_model(request, obj, form, change)

        # Only update balance for newly created deposits that are completed
        # (prevents accidentally adding the amount again when editing an existing deposit)
        if not change and obj.transaction_status == "Completed":
            try:
                account = obj.savings_account
                # Use Decimal for safety
                account.balance += Decimal(str(obj.amount))
                account.save(update_fields=["balance"])

                # Optional: success message in admin
                self.message_user(
                    request,
                    f"Balance updated successfully: +{obj.amount} to {account.account_number}",
                    messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to update account balance: {str(e)}",
                    messages.ERROR,
                )
