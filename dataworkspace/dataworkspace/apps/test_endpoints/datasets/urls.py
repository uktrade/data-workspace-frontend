from dataworkspace.apps.test_endpoints.datasets import views
from django.urls import path

urlpatterns = [
    path(
        "dataset/<uuid:pk>",
        views.EditDatasetCatalogueEditorsViewSet.as_view({"patch": "partial_update"}),
        name="update",
    ),
    path(
        "dataset/<uuid:pk>/delete-user-permissions",
        views.ResetDatasetUserPermissionsViewSet.as_view({"delete": "destroy"}),
        name="reset",
    ),
]
