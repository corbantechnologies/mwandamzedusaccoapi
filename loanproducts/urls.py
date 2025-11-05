from django.urls import path

from loanproducts.views import LoanProductDetailView, LoanProductListCreateView

app_name = "loanproducts"

urlpatterns = [
    path("", LoanProductListCreateView.as_view(), name="loanproducts"),
    path(
        "<str:reference>/", LoanProductDetailView.as_view(), name="loanproduct-detail"
    ),
]
