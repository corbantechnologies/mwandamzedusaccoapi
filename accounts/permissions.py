from rest_framework.permissions import BasePermission

SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]


class IsSystemAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS
            or request.user.is_authenticated
            and request.user.is_sacco_admin
            or request.user.is_sacco_staff
            or request.user.is_treasurer
            or request.user.is_bookkeeper
            or request.user.is_superuser
        )

    def has_object_permission(self, request, view, obj):
        return (
            request.method in SAFE_METHODS
            or request.user.is_authenticated
            and request.user.is_sacco_admin
            or request.user.is_sacco_staff
            or request.user.is_treasurer
            or request.user.is_bookkeeper
            or request.user.is_superuser
        )
