from django.urls import path, include
from detector.api_views import analyze

urlpatterns = [
    path("", include("detector.urls")),
    path("api/analyze", analyze, name="api_analyze"),
]
