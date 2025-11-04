from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAdmin(admin.ModelAdmin):
    list_display = [
        "member_no",
        "email",
        "first_name",
        "last_name",
        "is_approved",
        "is_member",
        "is_sacco_admin",
        "is_active",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "is_approved",
        "is_member",
        "is_sacco_admin",
        "is_active",
        "created_at",
        "updated_at",
    ]

    search_fields = [
        "member_no",
        "email",
        "first_name",
        "last_name",
    ]


admin.site.register(User, UserAdmin)
