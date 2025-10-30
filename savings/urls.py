from django.urls import path

from savings.views import SavingListCreateView, SavingDetailView

app_name = "savings"

urlpatterns = [
    path("", SavingListCreateView.as_view(), name="savings"),
    path("<str:reference>/", SavingDetailView.as_view(), name="saving-detail"),
]
