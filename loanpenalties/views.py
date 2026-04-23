from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError

from loanpenalties.models import LoanPenalty
from loanpenalties.serializers import LoanPenaltySerializer
from loanpenalties.services import apply_auto_targeted_penalty


class LoanPenaltyListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = LoanPenalty.objects.all()
    serializer_class = LoanPenaltySerializer
    filterset_fields = ["loan_account__reference", "loan_account__account_number"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        loan_account = serializer.validated_data["loan_account"]

        try:
            penalty = apply_auto_targeted_penalty(loan_account, request.user)
        except ValidationError as e:
            # Map Django's ValidationError to DRF's ValidationError
            error_message = e.message if hasattr(e, "message") else list(e.messages)
            raise DRFValidationError({"detail": error_message})

        result_serializer = self.get_serializer(penalty)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class LoanPenaltyRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = LoanPenalty.objects.all()
    serializer_class = LoanPenaltySerializer
    lookup_field = "reference"

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == "Waived":
            raise DRFValidationError(
                {"detail": "Cannot update a loan penalty that has been waived."}
            )
        return super().update(request, *args, **kwargs)
