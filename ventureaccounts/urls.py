from django.urls import path

from ventureaccounts.views import VentureAccountDetailView, VentureAccountListCreateView

app_name = "ventureaccounts"

urlpatterns = [
    path("", VentureAccountListCreateView.as_view(), name="ventures"),
    path("<str:reference>/", VentureAccountDetailView.as_view(), name="venture-detail"),
]
