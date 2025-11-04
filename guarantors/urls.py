from django.urls import path

from guarantors.views import GuarantorProfileDetailView, GuarantorProfileListCreateView

app_name = "guarantors"

urlpatterns = [
    path("", GuarantorProfileListCreateView.as_view(), name="guarantors"),
    path("<str:reference>/", GuarantorProfileDetailView.as_view(), name="guarantor-detail"),
]
