from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from cloudinary.models import CloudinaryField

from accounts.abstracts import (
    UniversalIdModel,
    MemberNumberModel,
    TimeStampedModel,
    ReferenceModel,
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, password, **extra_fields):
        user = self.model(**extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        return self._create_user(password, **extra_fields)

    def create_superuser(self, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_approved", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("is_approved") is not True:
            raise ValueError("Superuser must have is_approved=True.")

        return self._create_user(password, **extra_fields)


class User(
    AbstractBaseUser,
    PermissionsMixin,
    UniversalIdModel,
    TimeStampedModel,
    MemberNumberModel,
    ReferenceModel,
):
    # Personal Details
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    gender = models.CharField(max_length=255)
    dob = models.DateField(blank=True, null=True)
    avatar = CloudinaryField("mzedu_avatars", blank=True, null=True)

    # Identity
    id_type = models.CharField(max_length=255, blank=True, null=True)
    id_number = models.CharField(max_length=255, blank=True, null=True)
    tax_pin = models.CharField(max_length=255, blank=True, null=True)

    # Contact & Address Details
    phone = models.CharField(max_length=255, blank=True, null=True)
    county = models.CharField(max_length=255, blank=True, null=True)

    # Account status
    is_approved = models.BooleanField(default=False)

    # Permissions
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_member = models.BooleanField(default=True)
    is_sacco_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Password Reset
    password_reset_code = models.CharField(max_length=6, blank=True, null=True)
    password_reset_code_created_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = "member_no"
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "password",
        "email",
        "gender",
    ]

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_member_no(self):
        return self.member_no

    def __str__(self):
        return f"{self.member_no} - {self.first_name} {self.last_name}"
