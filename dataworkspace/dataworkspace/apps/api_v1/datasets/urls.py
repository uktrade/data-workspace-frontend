from django.urls import path
from dataworkspace.apps.api_v1.datasets.views import (
    APIDatasetView,
)

urlpatterns = [
    path(
        '<str:dataset_id>/<str:table_id>',
        APIDatasetView.as_view(),
        name='api-dataset-view',
    )
]
