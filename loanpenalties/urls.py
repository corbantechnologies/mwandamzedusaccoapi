from django.urls import path

from loanpenalties.views import LoanPenaltyListCreateView, LoanPenaltyRetrieveUpdateView

app_name = "loanpenalties"

urlpatterns = [
    path("", LoanPenaltyListCreateView.as_view(), name="loan-penalties"),
    path(
        "<str:reference>/",
        LoanPenaltyRetrieveUpdateView.as_view(),
        name="loan-penalty",
    ),
]
