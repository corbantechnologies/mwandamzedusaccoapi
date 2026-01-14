import logging
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from transactions.serializers import AccountSerializer

logger = logging.getLogger(__name__)

User = get_user_model()

class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated,]

    def get_queryset(self):
        return (
            User.objects.all().filter(is_member=True).prefetch_related(
                "venture_accounts",
                "savings",
                "loan_accounts",
            )
        )

class AccountDetailView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated,]
    lookup_field = "member_no"

    def get_queryset(self):
        return (
            User.objects.all().filter(is_member=True).prefetch_related(
                "venture_accounts",
                "savings",
                "loan_accounts",
            )
        )
