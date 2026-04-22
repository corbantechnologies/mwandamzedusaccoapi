from django.urls import path

from venturetypes.views import VentureTypeListView, VentureTypeDetailView

app_name = "venturetypes"

urlpatterns = [
    path("", VentureTypeListView.as_view(), name="venturetypes"),
    path(
        "<str:reference>/", VentureTypeDetailView.as_view(), name="venturetype-detail"
    ),
]
