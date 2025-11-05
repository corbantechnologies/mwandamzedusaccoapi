from rest_framework import serializers
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from accounts.validators import (
    validate_password_digit,
    validate_password_uppercase,
    validate_password_lowercase,
    validate_password_symbol,
)
from accounts.utils import send_account_created_by_admin_email
from mwandamzeduapi.settings import DOMAIN
from savings.serializers import SavingSerializer
from ventureaccounts.serializers import VentureAccountSerializer
from loanaccounts.serializers import LoanAccountSerializer
from loanapplications.serializers import LoanApplicationSerializer


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
    avatar = serializers.ImageField(use_url=True, required=False)
    savings = SavingSerializer(many=True, read_only=True)
    venture_accounts = VentureAccountSerializer(many=True, read_only=True)
    loan_accounts = LoanAccountSerializer(many=True, read_only=True)
    loan_applications = LoanApplicationSerializer(many=True, read_only=True)

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
