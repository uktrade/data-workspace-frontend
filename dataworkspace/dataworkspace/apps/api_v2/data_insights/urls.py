from django.urls import path

from dataworkspace.apps.api_v2.data_insights.views import OwnerInsightsViewSet

urlpatterns = [
    path(
        "owner_insights",
        OwnerInsightsViewSet.as_view({"get": "list"}),
        name="owner_insights",
    ),
]
