from rest_framework import serializers
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils import timezone
import secrets
import string
from datetime import datetime
from rest_framework.validators import UniqueValidator

from accounts.validators import (
    validate_password_digit,
    validate_password_uppercase,
    validate_password_lowercase,
    validate_password_symbol,
)
from accounts.utils import (
    send_account_created_by_admin_email,
    send_forgot_password_email,
    send_password_reset_success_email,
)
from mwandamzeduapi.settings import DOMAIN
from savings.serializers import SavingSerializer
from ventureaccounts.serializers import VentureAccountSerializer
from loanaccounts.serializers import LoanAccountSerializer
from loanapplications.serializers import LoanApplicationSerializer
from guarantors.serializers import GuarantorProfileSerializer


User = get_user_model()


class BaseUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        max_length=128,
        min_length=5,
        write_only=True,
        validators=[
            validate_password_digit,
            validate_password_uppercase,
            validate_password_symbol,
            validate_password_lowercase,
        ],
    )
    email = serializers.EmailField(required=True, validators=[UniqueValidator(queryset=User.objects.all())])
    avatar = serializers.ImageField(use_url=True, required=False)
    savings = SavingSerializer(many=True, read_only=True)
    venture_accounts = VentureAccountSerializer(many=True, read_only=True)
    loan_accounts = LoanAccountSerializer(many=True, read_only=True)
    loan_applications = LoanApplicationSerializer(many=True, read_only=True)
    guarantor_profile = GuarantorProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "member_no",
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "password",
            "dob",
            "gender",
            "avatar",
            "id_type",
            "id_number",
            "tax_pin",
            "phone",
            "county",
            "is_approved",
            "is_staff",
            "is_superuser",
            "is_member",
            "is_sacco_admin",
            "is_active",
            "created_at",
            "updated_at",
            "reference",
            "guarantor_profile",
            "savings",
            "venture_accounts",
            "loan_accounts",
            "loan_applications",
        )

    def create_user(self, validated_data, role_field):
        user = User.objects.create_user(**validated_data)
        setattr(user, role_field, True)
        user.is_active = True
        user.save()

        return user


"""
Normal login
"""


class UserLoginSerializer(serializers.Serializer):
    member_no = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


"""
SACCO Admins Serializers
- They can create new members.
- The members are already approved.
- A password has to be set or they reset.
"""


class MemberCreatedByAdminSerializer(BaseUserSerializer):
    password = serializers.CharField(required=False, write_only=True)
    email = serializers.EmailField(required=False)

    def create(self, validated_data):
        # validated_data["password"] = None
        user = self.create_user(validated_data, "is_member")
        user.is_approved = True
        user.save()

        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        activation_link = f"{DOMAIN}/activate/{uid}/{token}"

        # Send member number email if email is provided
        if validated_data.get("email"):
            send_account_created_by_admin_email(user, activation_link)

        return user


class BulkMemberCreatedByAdminSerializer(serializers.Serializer):
    members = MemberCreatedByAdminSerializer(many=True)

    def create(self, validated_data):
        members_data = validated_data.get("members", [])
        created_members = []

        for member_data in members_data:
            serializer = MemberCreatedByAdminSerializer(data=member_data)
            serializer.is_valid(raise_exception=True)
            member = serializer.save()
            created_members.append(member)

        return created_members


"""
Passwords
"""


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(
        max_length=128,
        min_length=5,
        write_only=True,
        validators=[
            validate_password_digit,
            validate_password_uppercase,
            validate_password_symbol,
            validate_password_lowercase,
        ],
    )

    def validate(self, attrs):
        user = self.instance  # Use self.instance instead of context
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError(
                {"old_password": "Incorrect old password"}
            )
        return attrs

    def save(self):
        user = self.instance
        password = self.validated_data.get("password")
        user.set_password(password)
        user.save()
        # TODO: clear session
        update_session_auth_hash(self.context["request"], user)  # Maintain session
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")
        return value
        

    def save(self):
        email = self.validated_data["email"]
        user = User.objects.get(email=email)
        
        # Generate 6-digit code
        code = "".join(secrets.choice(string.digits) for _ in range(6))
        user.password_reset_code = code
        user.password_reset_code_created_at = timezone.now()
        user.save()

        # Send email
        send_forgot_password_email(user, code)
        return user


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6)
    password = serializers.CharField(
        max_length=128,
        min_length=5,
        write_only=True,
        validators=[
            validate_password_digit,
            validate_password_uppercase,
            validate_password_symbol,
            validate_password_lowercase,
        ],
    )

    def validate(self, attrs):
        email = attrs.get("email")
        code = attrs.get("code")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")

        if user.password_reset_code != code:
            raise serializers.ValidationError("Invalid reset code")

        if not user.password_reset_code_created_at:
             raise serializers.ValidationError("No reset code request found")
             
        # Check for expiry (e.g., 15 minutes)
        # Using timezone.now() to ensure we compare aware checks if project is aware
        created_at = user.password_reset_code_created_at
        now = timezone.now()
        
        if created_at + timezone.timedelta(minutes=15) < now:
             raise serializers.ValidationError("Reset code has expired")
        
        return attrs

    def save(self):
        email = self.validated_data["email"]
        password = self.validated_data["password"]
        
        user = User.objects.get(email=email)
        user.set_password(password)
        user.password_reset_code = None
        user.password_reset_code_created_at = None
        user.save()
        
        # Send success email
        send_password_reset_success_email(user)
        
        return user