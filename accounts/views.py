import csv
import io
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import HttpResponse
from rest_framework.authtoken.models import Token
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from accounts.serializers import (
    UserLoginSerializer,
    BaseUserSerializer,
    MemberCreatedByAdminSerializer,
    PasswordChangeSerializer,
    ForgotPasswordSerializer,
    AdminResetPasswordSerializer,
    ResetPasswordSerializer,
    BulkMemberCreatedByAdminSerializer,
    BulkMemberCreatedByAdminUploadCSVSerializer,
)
from accounts.utils import send_account_activated_email
from accounts.tools import create_member_accounts
from accounts.permissions import IsSystemAdminOrReadOnly
from mwandamzedusaccoapi.settings import DOMAIN
from savingtypes.models import SavingType
from venturetypes.models import VentureType
from savings.models import SavingsAccount
from ventureaccounts.models import VentureAccount

User = get_user_model()

logger = logging.getLogger(__name__)


class TokenView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = UserLoginSerializer

    def post(self, request, format=None):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            member_no = serializer.validated_data["member_no"]
            password = serializer.validated_data["password"]

            user = authenticate(member_no=member_no, password=password)

            # TODO: Implement 2FA, OTP, or token expiration

            if user:
                if user.is_approved:
                    token, created = Token.objects.get_or_create(user=user)
                    user_details = {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "member_no": user.member_no,
                        "reference": user.reference,
                        "is_member": user.is_member,
                        "is_sacco_admin": user.is_sacco_admin,
                        "is_active": user.is_active,
                        "is_staff": user.is_staff,
                        "is_superuser": user.is_superuser,
                        "is_approved": user.is_approved,
                        "last_login": user.last_login,
                        "token": token.key,
                    }
                    return Response(user_details, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"detail": ("User account is not verified.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"detail": ("Unable to log in with provided credentials.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


"""
Member Views
"""


class UserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(id=self.request.user.id)
            .prefetch_related(
                "venture_accounts",
                "savings",
                "loan_applications",
                "loan_accounts",
                "guarantor_profile",
            )
        )


class PasswordChangeView(generics.UpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = PasswordChangeSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {"detail": "Password changed successfully"}, status=status.HTTP_200_OK
        )


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Reset code sent to your email"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password has been reset successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


"""
SACCO Admin
- create members
- approve members
"""


class MemberListView(generics.ListAPIView):
    """
    Fetch the list of members
    """

    permission_classes = (IsSystemAdminOrReadOnly,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()

    def get_queryset(self):
        """
        Fetch is_member and is_sacco_admin field
        Users with is_sacco_admin are also members
        """
        return super().get_queryset().filter(is_member=True).prefetch_related(
            "venture_accounts",
            "savings",
            "loan_applications",
            "loan_accounts",
            "guarantor_profile",
        ) | super().get_queryset().filter(is_sacco_admin=True).prefetch_related(
            "venture_accounts",
            "savings",
            "loan_applications",
            "loan_accounts",
            "guarantor_profile",
        )


class MemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update and delete a member
    """

    permission_classes = (IsSystemAdminOrReadOnly,)
    serializer_class = BaseUserSerializer
    queryset = User.objects.all()
    lookup_field = "member_no"


class MemberCreatedByAdminView(generics.CreateAPIView):
    permission_classes = (IsSystemAdminOrReadOnly,)
    serializer_class = MemberCreatedByAdminSerializer
    queryset = User.objects.all()

    def perform_create(self, serializer):
        user = serializer.save()
        create_member_accounts(user)


class BulkMemberCreatedByAdminView(APIView):
    permission_classes = (IsSystemAdminOrReadOnly,)

    def post(self, request):
        serializer = BulkMemberCreatedByAdminSerializer(data=request.data)
        if serializer.is_valid():
            users = serializer.save()
            for user in users:
                create_member_accounts(user)
            return Response(
                {
                    "detail": "Members created successfully",
                    "members": MemberCreatedByAdminSerializer(users, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BulkMemberCreatedByAdminUploadCSVView(generics.GenericAPIView):
    permission_classes = (IsSystemAdminOrReadOnly,)
    serializer_class = BulkMemberCreatedByAdminUploadCSVSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        csv_file = serializer.validated_data["csv_file"]
        decoded_file = csv_file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created_users = []
        errors = []

        for row_number, row in enumerate(reader, start=2):  # Row 1 = headers
            # Clean data: remove empty strings so optional fields are handled correctly
            data = {k: v.strip() for k, v in row.items() if v and v.strip()}

            # Identify the row for better error reporting
            identifier = row.get("email") or row.get("member_no") or f"Row {row_number}"

            member_serializer = MemberCreatedByAdminSerializer(data=data)
            if member_serializer.is_valid():
                try:
                    user = member_serializer.save()
                    create_member_accounts(user)
                    created_users.append(user)
                except Exception as e:
                    errors.append(
                        f"Row {row_number} ({identifier}): Error creating user - {str(e)}"
                    )
            else:
                # Make validation errors more readable
                error_details = []
                for field, msgs in member_serializer.errors.items():
                    error_details.append(
                        f"{field}: {', '.join([str(m) for m in msgs])}"
                    )
                errors.append(
                    f"Row {row_number} ({identifier}): Validation error - {'; '.join(error_details)}"
                )

        # Prepare response data
        total_rows = len(created_users) + len(errors)
        response_data = {
            "success": len(errors) == 0 and len(created_users) > 0,
            "message": f"Processed CSV: {len(created_users)} created, {len(errors)} failed out of {total_rows}.",
            "created_count": len(created_users),
            "failed_count": len(errors),
        }

        if errors:
            response_data["errors"] = errors

        # Determine appropriate HTTP status code
        if created_users:
            # At least one user was created
            if len(errors) == 0:
                status_code = status.HTTP_201_CREATED
            else:
                status_code = status.HTTP_200_OK
        else:
            # Nothing was created → treat as client error
            status_code = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=status_code)


class BulkMemberUploadCSVTemplateView(APIView):
    permission_classes = (IsSystemAdminOrReadOnly,)

    def get(self, request):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="member_upload_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "first_name",
                "last_name",
                "member_no",
                "email",
                "gender",
                "phone",
                "payroll_number",
                "employer",
            ]
        )

        return response


class ActivateAccountView(APIView):
    permission_classes = [
        AllowAny,
    ]

    def patch(self, request):
        uidb64 = request.data.get("uidb64")
        token = request.data.get("token")
        password = request.data.get("password")

        if not all([uidb64, token, password]):
            return Response(
                {"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"error": "Invalid activation link"}, status=status.HTTP_400_BAD_REQUEST
            )

        token_generator = PasswordResetTokenGenerator()
        if token_generator.check_token(user, token):
            # Validate password using the serializer
            serializer = BaseUserSerializer(
                user, data={"password": password}, partial=True
            )
            if serializer.is_valid():
                user.set_password(password)
                user.is_active = True
                user.save()

                # Send member number email
                try:
                    send_account_activated_email(user)
                except Exception as e:
                    # Log the error (use your preferred logging mechanism)
                    logger.error(f"Failed to send email to {user.email}: {str(e)}")
                    # print(f"Failed to send email to {user.email}: {str(e)}")
                return Response(
                    {"message": "Account activated successfully"},
                    status=status.HTTP_200_OK,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST
        )


class AdminResetPasswordView(generics.UpdateAPIView):
    """
    Allow admins to reset the password for a member.
    """

    permission_classes = (IsSystemAdminOrReadOnly,)
    serializer_class = AdminResetPasswordSerializer
    queryset = User.objects.all()
    lookup_field = "member_no"

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        return Response(
            {"message": "Password reset successfully."}, status=status.HTTP_200_OK
        )
