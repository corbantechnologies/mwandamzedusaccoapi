from django.urls import path

from loanproducts.views import LoanProductDetailView, LoanProductListView

app_name = "loanproducts"

urlpatterns = [
    path("", LoanProductListView.as_view(), name="loanproducts"),
    path(
        "<str:reference>/", LoanProductDetailView.as_view(), name="loanproduct-detail"
    ),
]
