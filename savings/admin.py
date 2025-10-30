from django.contrib import admin

from savings.models import Saving

class SavingAdmin(admin.ModelAdmin):
    list_display = ('member', 'account_number', 'account_type', 'balance', 'is_active')
    search_fields = ('member__member_no', 'account_number')


admin.site.register(Saving, SavingAdmin)
