from django.urls import path

from loanaccounts.views import LoanAccountDetailView, LoanAccountListCreateView

app_name = "loanaccounts"

urlpatterns = [
    path("", LoanAccountListCreateView.as_view(), name="loanaccounts"),
    path(
        "<str:reference>/", LoanAccountDetailView.as_view(), name="loanaccount-detail"
    ),
]
