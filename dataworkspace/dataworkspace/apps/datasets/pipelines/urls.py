from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.pipelines import views


urlpatterns = [
    path("", login_required(views.PipelineListView.as_view()), name="index"),
    path(
        "create",
        login_required(views.PipelineCreateView.as_view()),
        name="create",
    ),
    path(
        "<int:pk>/edit",
        login_required(views.PipelineUpdateView.as_view()),
        name="edit",
    ),
    path(
        "<int:pk>/delete",
        login_required(views.PipelineDeleteView.as_view()),
        name="delete",
    ),
    path(
        "<int:pk>/run",
        login_required(views.PipelineRunView.as_view()),
        name="run",
    ),
    path(
        "<int:pk>/stop",
        login_required(views.PipelineStopView.as_view()),
        name="stop",
    ),
    path(
        "<int:pk>/logs",
        login_required(views.PipelineLogsDetailView.as_view()),
        name="logs",
    ),
]
