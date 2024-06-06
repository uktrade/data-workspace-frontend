from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.request_access.views import (
    AccessRequestConfirmationPage,
    AccessRequestSummaryPage,
    DatasetAccessRequest,
    DatasetAccessRequestUpdate,
    SelfCertifyView,
    ToolsAccessRequestPart1,
    ToolsAccessRequestPart2,
    ToolsAccessRequestPart3,
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
        login_required(ToolsAccessRequestPart1.as_view()),
        name="tools-1",
    ),
    path(
        "<int:pk>/spss-stata",
        login_required(ToolsAccessRequestPart2.as_view()),
        name="tools-2",
    ),
    path(
        "<int:pk>/spss-stata-reason",
        login_required(ToolsAccessRequestPart3.as_view()),
        name="tools-3",
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
]
