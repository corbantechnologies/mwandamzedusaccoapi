from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/savingtypes/", include("savingtypes.urls")),
    path("api/v1/savings/", include("savings.urls")),
    path("api/v1/savingsdeposits/", include("savingsdeposits.urls")),
    path("api/v1/venturetypes/", include("venturetypes.urls")),
    path("api/v1/ventureaccounts/", include("ventureaccounts.urls")),
    path("api/v1/venturedeposits/", include("venturedeposits.urls")),
    path("api/v1/venturepayments/", include("venturepayments.urls")),
    path("api/v1/loanproducts/", include("loanproducts.urls")),
    path("api/v1/loanaccounts/", include("loanaccounts.urls")),
    path("api/v1/loanapplications/", include("loanapplications.urls")),
    path("api/v1/guarantors/", include("guarantors.urls")),
    path("api/v1/guaranteerequests/", include("guaranteerequests.urls")),
]
