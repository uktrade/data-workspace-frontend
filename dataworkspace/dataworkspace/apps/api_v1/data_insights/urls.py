from dataworkspace.apps.api_v1.data_insights.views import OwnerInsightsViewSet

from django.urls import path

urlpatterns = [
    path(
        "owners/insights",
        OwnerInsightsViewSet.as_view({"get": "get_owner_insights"}),
        name="owners-insights",
    ),
]