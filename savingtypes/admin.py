from django.contrib import admin

from savingtypes.models import SavingType

class SavingTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'is_active')
    search_fields = ('name',)

admin.site.register(SavingType, SavingTypeAdmin)
