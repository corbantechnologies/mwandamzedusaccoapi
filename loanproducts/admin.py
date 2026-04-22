from django.contrib import admin

from loanproducts.models import LoanProduct


class LoanProductAdmin(admin.ModelAdmin):
    list_display = ["name", "interest_rate", "interest_period", "calculation_schedule"]
    search_fields = ["name", "interest_rate", "interest_period", "calculation_schedule"]


admin.site.register(LoanProduct, LoanProductAdmin)
