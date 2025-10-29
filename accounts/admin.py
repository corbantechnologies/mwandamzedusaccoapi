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
    ]


admin.site.register(User, UserAdmin)
