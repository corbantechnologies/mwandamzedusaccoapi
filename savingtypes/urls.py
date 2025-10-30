from django.urls import path

from savingtypes.views import SavingTypeListCreateView, SavingTypeDetailView

app_name = "savingtypes"

urlpatterns = [
    path("", SavingTypeListCreateView.as_view(), name="savingtypes"),
    path("<str:reference>/", SavingTypeDetailView.as_view(), name="savingtype-detail"),
]