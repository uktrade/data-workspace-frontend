from django.urls import path

# pylint: disable=consider-using-from-import
import dataworkspace.apps.api_v1.datasets.views as views

urlpatterns = [
    path(
        "catalogue-items",
        views.CatalogueItemsInstanceViewSet.as_view({"get": "list"}),
        name="catalogue-items",
    ),
    path(
        "source-link",
        views.dataset_source_link_api_view_POST,
        name="api-dataset-source-link",
    ),
    path(
        "<str:dataset_id>/<str:source_table_id>",
        views.dataset_api_view_GET,
        name="api-dataset-view",
    ),
    path(
        "<str:group_slug>/reference/<str:reference_slug>",
        views.reference_dataset_api_view_GET,
        name="api-reference-dataset-view",
    ),
    path(
        "tool-query-audit-logs",
        views.ToolQueryAuditLogViewSet.as_view({"get": "list"}),
        name="tool-query-audit-logs",
    ),
]
