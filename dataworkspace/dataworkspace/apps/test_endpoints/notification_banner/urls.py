from dataworkspace.apps.test_endpoints.notification_banner import views

from django.urls import path

urlpatterns = [
    path(
        "notification/<int:pk>",
        views.UpdateNotificationBanner.as_view({"patch": "partial_update"}),
        name="update",
    ),
]
