from django.urls import path

from loanapplications.views import (
    LoanApplicationDetailView,
    LoanApplicationListCreateView,
    SubmitLoanApplicationView,
    ApproveOrDeclineLoanApplicationView,
    SubmitForAmendmentView,
    AmendApplicationView,
    AcceptAmendmentView,
    CancelApplicationView,
)

app_name = "loanapplications"

urlpatterns = [
    path("", LoanApplicationListCreateView.as_view(), name="loanapplications"),
    path(
        "<str:reference>/",
        LoanApplicationDetailView.as_view(),
        name="loanapplication-detail",
    ),
    path(
        "<str:reference>/submit-amendment/",
        SubmitForAmendmentView.as_view(),
        name="submit-for-amendment",
    ),
    path(
        "<str:reference>/amend/",
        AmendApplicationView.as_view(),
        name="amend-application",
    ),
    path(
        "<str:reference>/accept-amendment/",
        AcceptAmendmentView.as_view(),
        name="accept-amendment",
    ),
    path(
        "<str:reference>/cancel/",
        CancelApplicationView.as_view(),
        name="cancel-application",
    ),
    path(
        "<str:reference>/submit/",
        SubmitLoanApplicationView.as_view(),
        name="submit-loanapplication",
    ),
    path(
        "<str:reference>/status/",
        ApproveOrDeclineLoanApplicationView.as_view(),
        name="approve-or-decline-loanapplication",
    ),
]
