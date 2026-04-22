from django.contrib import admin

from venturetypes.models import VentureType


class VentureTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "interest_rate")
    search_fields = ("name",)


admin.site.register(VentureType, VentureTypeAdmin)
