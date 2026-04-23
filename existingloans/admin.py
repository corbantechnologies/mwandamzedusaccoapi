from django.contrib import admin

from existingloans.models import ExistingLoan


@admin.register(ExistingLoan)
class ExistingLoanAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "account_number",
        "principal",
        "outstanding_balance",
        "total_amount_paid",
        "status",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("member__username", "account_number")
    ordering = ("-created_at",)
