from django.urls import path

from dataworkspace.apps.api_v1.data_insights.views import DataInsightsViewSet

urlpatterns = [
    path("data-insights", DataInsightsViewSet.as_view({"get": "list"}), name="data-insights")
]
