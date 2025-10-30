import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from accounts.serializers import (
    UserLoginSerializer,
    BaseUserSerializer,
    MemberCreatedByAdminSerializer,
    PasswordChangeSerializer
)
from accounts.utils import send_account_activated_email
from accounts.permissions import IsSystemAdminOrReadOnly
from mwandamzeduapi.settings import DOMAIN
from savingtypes.models import SavingType
from venturetypes.models import VentureType
from savings.models import Saving
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
        return super().get_queryset().filter(id=self.request.user.id)


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
        return super().get_queryset().filter(
            is_member=True
        ) | super().get_queryset().filter(is_sacco_admin=True)


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

        # Existing savings account creation
        savings_types = SavingType.objects.all()
        created_accounts = []
        for savings_type in savings_types:
            if not Saving.objects.filter(
                member=user, account_type=savings_type
            ).exists():
                account = Saving.objects.create(
                    member=user, account_type=savings_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccounts for {user.member_no}: {', '.join(created_accounts)}"
        )
        # Existing venture account creation
        venture_types = VentureType.objects.all()
        created_accounts = []
        for venture_type in venture_types:
            if not VentureAccount.objects.filter(
                member=user, venture_type=venture_type
            ).exists():
                account = VentureAccount.objects.create(
                    member=user, venture_type=venture_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} VentureAccounts for {user.member_no}: {', '.join(created_accounts)}"
        )


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
