from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.request_access.views import (
    AccessRequestConfirmationPage,
    AccessRequestSummaryPage,
    DatasetAccessRequest,
    DatasetAccessRequestUpdate,
    SelfCertifyView,
    StataAccessRequest,
    StataAccessView,
    ToolsAccessRequest,
)

urlpatterns = [
    path(
        "",
        login_required(DatasetAccessRequest.as_view()),
        name="index",
    ),
    path(
        "<uuid:dataset_uuid>",
        login_required(DatasetAccessRequest.as_view()),
        name="dataset",
    ),
    path(
        "<int:pk>/dataset",
        login_required(DatasetAccessRequestUpdate.as_view()),
        name="dataset-request-update",
    ),
    path(
        "<int:pk>/tools",
        login_required(ToolsAccessRequest.as_view()),
        name="tools",
    ),
    path(
        "<int:pk>/summary",
        login_required(AccessRequestSummaryPage.as_view()),
        name="summary-page",
    ),
    path(
        "<int:pk>/confirmation",
        login_required(AccessRequestConfirmationPage.as_view()),
        name="confirmation-page",
    ),
    path(
        "self-certify",
        login_required(SelfCertifyView.as_view()),
        name="self-certify-page",
    ),
    path(
        "stata-access",
        login_required(StataAccessRequest.as_view()),
        name="stata-access-index",
    ),
    path(
        "<int:pk>/stata-access",
        login_required(StataAccessView.as_view()),
        name="stata-access-page",
    ),
]
