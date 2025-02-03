from django.urls import path

from dataworkspace.apps.api_v2.inline_feedback import views

urlpatterns = [
    path(
        "inline_feedback", views.InlineFeedBackViewSet.as_view({"post": "create"}), name="create"
    ),
    path(
        "inline_feedback/<int:pk>",
        views.InlineFeedBackViewSet.as_view({"patch": "partial_update"}),
        name="update",
    ),
]
