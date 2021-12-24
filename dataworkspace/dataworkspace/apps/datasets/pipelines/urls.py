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
]
