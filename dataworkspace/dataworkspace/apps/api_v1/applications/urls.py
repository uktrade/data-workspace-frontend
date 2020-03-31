from django.urls import path

from dataworkspace.apps.api_v1.applications.views import (
    ApplicationInstanceReportViewSet,
)

urlpatterns = [
    path(
        'instances',
        ApplicationInstanceReportViewSet.as_view({'get': 'list'}),
        name='instances',
    )
]
