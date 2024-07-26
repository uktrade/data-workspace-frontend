from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.pipelines import views
from dataworkspace.apps.datasets.pipelines.forms import (
    SQLPipelineCreateForm,
    SQLPipelineEditForm,
    SharepointPipelineCreateForm,
    SharepointPipelineEditForm,
)

urlpatterns = [
    path("", login_required(views.PipelineListView.as_view()), name="index"),
    path(
        "create",
        login_required(views.PipelineSelectTypeView.as_view()),
        name="create",
    ),
    path(
        "create/sql",
        login_required(views.PipelineCreateView.as_view()),
        {"form_class": SQLPipelineCreateForm},
        name="create-sql",
    ),
    path(
        "create/sharepoint",
        login_required(views.PipelineCreateView.as_view()),
        {"form_class": SharepointPipelineCreateForm},
        name="create-sharepoint",
    ),
    path(
        "<int:pk>/sql/edit",
        login_required(views.PipelineUpdateView.as_view()),
        {"form_class": SQLPipelineEditForm},
        name="edit-sql",
    ),
    path(
        "<int:pk>/sharepoint/edit",
        login_required(views.PipelineUpdateView.as_view()),
        {"form_class": SharepointPipelineEditForm},
        name="edit-sharepoint",
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
]
