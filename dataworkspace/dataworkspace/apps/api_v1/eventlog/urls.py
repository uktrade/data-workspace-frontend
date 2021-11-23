from django.urls import path

from dataworkspace.apps.api_v1.eventlog.views import EventLogViewSet

urlpatterns = [path("events", EventLogViewSet.as_view({"get": "list"}), name="events")]
