from dataworkspace.apps.test_endpoints.datasets import views
from django.urls import path

urlpatterns = [
    path(
        "dataset/<uuid:pk>",
        views.DatasetViewSet.as_view({"patch": "partial_update"}),
        name="update",
    )
]
