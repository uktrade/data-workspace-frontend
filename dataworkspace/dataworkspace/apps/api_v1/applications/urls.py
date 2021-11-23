from django.urls import path

from dataworkspace.apps.api_v1.applications.views import ApplicationInstanceViewSet

urlpatterns = [
    path(
        "instances",
        ApplicationInstanceViewSet.as_view({"get": "list"}),
        name="instances",
    )
]
