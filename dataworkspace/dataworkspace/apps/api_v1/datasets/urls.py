from django.urls import path

import dataworkspace.apps.api_v1.datasets.views as views

urlpatterns = [
    path(
        '<str:dataset_id>/<str:source_table_id>',
        views.dataset_api_view_GET,
        name='api-dataset-view',
    ),
    path(
        '<str:group_slug>/reference/<str:reference_slug>',
        views.reference_dataset_api_view_GET,
        name='api-reference-dataset-view',
    ),
]
