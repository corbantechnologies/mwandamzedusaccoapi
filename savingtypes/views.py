import logging

from django.contrib.auth import get_user_model
from rest_framework import generics

from savingtypes.models import SavingType
from savingtypes.serializers import SavingTypeSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from savings.models import SavingsAccount

logger = logging.getLogger(__name__)

User = get_user_model()


class SavingTypeListCreateView(generics.ListCreateAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)

    def perform_create(self, serializer):
        saving_types = serializer.save()
        members = User.objects.filter(is_member=True)
        created_accounts = []

        for member in members:
            if not SavingsAccount.objects.filter(
                member=member, account_type=saving_types
            ).exists():
                account = SavingsAccount.objects.create(
                    member=member, account_type=saving_types, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccount Accounts {', '.join(created_accounts)}"
        )


class SavingTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingType.objects.all()
    serializer_class = SavingTypeSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"
