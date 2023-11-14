from django.urls import include, path

urlpatterns = [
    path("", include(("dataworkspace.apps.api_v2.datasets.urls", "api_v2"), namespace="datasets")),
    path(
        "",
        include(
            ("dataworkspace.apps.api_v2.data_collections.urls", "api_v2"), namespace="collections"
        ),
    ),
]
