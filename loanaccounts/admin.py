from django.contrib import admin

from loanaccounts.models import LoanAccount


class LoanAccountAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "product",
        "account_number",
        "principal",
        "outstanding_balance",
        "start_date",
        "end_date",
        "status",
    )
    search_fields = (
        "member__member_no",
        "account_number",
        "product__name",
        "status",
    )
    list_filter = ("status", "product", "created_at")


admin.site.register(LoanAccount, LoanAccountAdmin)
