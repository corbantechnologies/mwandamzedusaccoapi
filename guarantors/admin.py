from django.contrib import admin
from django.utils import timezone
from django.core.exceptions import ValidationError

from guarantors.models import GuarantorProfile


@admin.register(GuarantorProfile)
class GuarantorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "is_eligible",
        "max_active_guarantees",
        "eligibility_checked_at",
    )
    list_filter = ("is_eligible", "max_active_guarantees")
    search_fields = ("member__member_no", "member__first_name", "member__last_name")
    readonly_fields = ("eligibility_checked_at",)

    actions = ["enable_guarantor", "disable_guarantor"]

    def enable_guarantor(self, request, queryset):
        updated = 0
        for profile in queryset:
            profile.is_eligible = True
            profile.eligibility_checked_at = timezone.now()
            try:
                profile.full_clean()
                profile.save()
                updated += 1
            except ValidationError as e:
                self.message_user(request, f"{profile.member}: {e}", level="error")
        self.message_user(request, f"{updated} members enabled as guarantors.")

    enable_guarantor.short_description = "Enable as Guarantor"

    def disable_guarantor(self, request, queryset):
        count = queryset.update(is_eligible=False, eligibility_checked_at=None)
        self.message_user(request, f"{count} members disabled.")

    disable_guarantor.short_description = "Disable as Guarantor"
