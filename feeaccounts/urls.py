from django.urls import path

from feeaccounts.views import FeeAccountListCreateView, FeeAccountDetailView

app_name = "feeaccounts"

urlpatterns = [
    path("", FeeAccountListCreateView.as_view(), name="feeaccount-list-create"),
    path("<str:reference>", FeeAccountDetailView.as_view(), name="feeaccount-detail"),
]
