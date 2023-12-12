from django.urls import include, path

urlpatterns = [
    path("", include(("dataworkspace.apps.api_v2.datasets.urls", "api_v2"), namespace="datasets")),
    path(
        "",
        include(
            ("dataworkspace.apps.api_v2.data_collections.urls", "api_v2"), namespace="collections"
        ),
    ),
    path(
        "",
        include(
            ("dataworkspace.apps.api_v2.recent_items.urls", "api_v2"), namespace="recent_items"
        ),
    ),
    path(
        "",
        include(
            ("dataworkspace.apps.api_v2.your_bookmarks.urls", "api_v2"), namespace="your_bookmarks"
        ),
    ),
    path(
        "",
        include(
            ("dataworkspace.apps.api_v2.recent_tools.urls", "api_v2"), namespace="recent_tools"
        ),
    ),
]
