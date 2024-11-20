from django.conf import settings
from django.urls import include, path

urlpatterns = []

if settings.ENVIRONMENT == "Dev":
    urlpatterns += [
        path(
            "",
            include(
                ("dataworkspace.apps.test_endpoints.datasets.urls", "test"), namespace="dataset"
            ),
        ),
    ]
