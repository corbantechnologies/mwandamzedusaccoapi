from django.contrib import admin

from loanapplications.models import LoanApplication


class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "member",
        "product",
        "requested_amount",
        "term_months",
        "repayment_frequency",
        "status",
        "created_at",
    ]
    search_fields = ["member__member_no", "product__name", "status"]
    list_filter = ("status", "product", "created_at")


admin.site.register(LoanApplication, LoanApplicationAdmin)
