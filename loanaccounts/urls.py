from django.urls import path

from loanaccounts.views import (
    LoanAccountDetailView,
    LoanAccountListCreateView,
    LoanPayoffQuoteView,
)

app_name = "loanaccounts"

urlpatterns = [
    path("", LoanAccountListCreateView.as_view(), name="loanaccounts"),
    path(
        "<str:reference>/", LoanAccountDetailView.as_view(), name="loanaccount-detail"
    ),
    path(
        "<str:reference>/payoff-quote/",
        LoanPayoffQuoteView.as_view(),
        name="loan_payoff_quote",
    ),
]
