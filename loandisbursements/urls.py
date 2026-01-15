from django.urls import path

from loandisbursements.views import LoanDisbursementListCreateView, LoanDisbursementDetailView

app_name = "loandisbursements"

urlpatterns = [
    path("", LoanDisbursementListCreateView.as_view(), name="list-create"),
    path("<str:reference>/", LoanDisbursementDetailView.as_view(), name="detail"),
]