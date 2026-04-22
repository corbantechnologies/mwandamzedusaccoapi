from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAdmin(admin.ModelAdmin):
    list_display = (
        "member_no",
        "email",
        "first_name",
        "last_name",
        "is_member",
        "is_sacco_admin",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_approved",
    )
    list_filter = (
        "is_member",
        "is_sacco_admin",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_approved",
    )
    search_fields = ("member_no", "email", "first_name", "last_name")
    ordering = ("member_no",)


admin.site.register(User, UserAdmin)
