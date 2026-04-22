from django.contrib import admin

from feeaccounts.models import FeeAccount


class FeeAccountAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "fee_type",
        "account_number",
        "amount_paid",
        "outstanding_balance",
        "is_paid",
    )
    search_fields = ("member__member_no", "account_number")
    list_filter = ("member", "fee_type", "is_paid")


admin.site.register(FeeAccount, FeeAccountAdmin)
