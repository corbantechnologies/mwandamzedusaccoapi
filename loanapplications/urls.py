from django.urls import path

from loanapplications.views import (
    LoanApplicationDetailView,
    LoanApplicationListCreateView,
    SubmitLoanApplicationView,
    ApproveOrDeclineLoanApplicationView,
    SubmitForAmendmentView,
    AmendApplicationView,
    FinalizeAmendmentView,
    AcceptAmendmentView,
    CancelApplicationView,
    AdminCreateLoanApplicationView,
    AdminLoanApplicationTemplateDownloadView,
    BulkAdminLoanApplicationUploadView,
    BulkAdminLoanApplicationCreateView,
)

app_name = "loanapplications"

urlpatterns = [
    path("", LoanApplicationListCreateView.as_view(), name="loanapplications"),
    path(
        "admin/create/",
        AdminCreateLoanApplicationView.as_view(),
        name="admin-create-loanapplication",
    ),
    path(
        "admin/bulk/template/",
        AdminLoanApplicationTemplateDownloadView.as_view(),
        name="admin-bulk-template",
    ),
    path(
        "admin/bulk/upload/",
        BulkAdminLoanApplicationUploadView.as_view(),
        name="admin-bulk-upload",
    ),
    path(
        "admin/bulk/create/",
        BulkAdminLoanApplicationCreateView.as_view(),
        name="admin-bulk-create",
    ),
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
        "<str:reference>/finalize-amendment/",
        FinalizeAmendmentView.as_view(),
        name="finalize-amendment",
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
