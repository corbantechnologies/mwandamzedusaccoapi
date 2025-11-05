from rest_framework import generics, status
from rest_framework.response import Response
from loanapplications.models import LoanApplication
from loanapplications.serializers import LoanApplicationSerializer
from rest_framework.permissions import IsAuthenticated


class LoanApplicationListCreateView(generics.ListCreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)


class LoanApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class SubmitLoanApplicationView(generics.GenericAPIView):
    """
    POST /api/v1/loanapplications/<reference>/submit/
    Submits a loan application if it's in 'Ready for Submission' state.
    """

    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        application = self.get_object()

        # Only owner can submit
        if application.member != request.user:
            return Response(
                {"detail": "You can only submit your own applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Must be Ready for Submission
        if application.status != "Ready for Submission":
            return Response(
                {"detail": "Application is not ready for submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent double submission
        if application.status == "Submitted":
            return Response(
                {"detail": "Application already submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Submit
        application.status = "Submitted"
        application.save(update_fields=["status"])

        serializer = self.get_serializer(application)
        return Response(
            {
                "detail": "Loan application submitted successfully.",
                "application": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
