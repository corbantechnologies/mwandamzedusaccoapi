import logging

from django.contrib.auth import get_user_model
from rest_framework import generics

from venturetypes.models import VentureType
from accounts.permissions import IsSystemAdminOrReadOnly
from venturetypes.serializers import VentureTypeSerializer
from ventureaccounts.models import VentureAccount

logger = logging.getLogger(__name__)

User = get_user_model()


class VentureTypeListView(generics.ListCreateAPIView):
    queryset = VentureType.objects.all()
    serializer_class = VentureTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        venture_type = serializer.save()
        members = User.objects.filter(is_member=True)
        created_accounts = []

        for member in members:
            if not VentureAccount.objects.filter(
                member=member, venture_type=venture_type
            ).exists():
                account = VentureAccount.objects.create(
                    member=member, venture_type=venture_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} Venture Accounts {', '.join(created_accounts)}"
        )


class VentureTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = VentureType.objects.all()
    serializer_class = VentureTypeSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"
