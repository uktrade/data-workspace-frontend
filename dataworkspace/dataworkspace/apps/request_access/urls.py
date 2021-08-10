from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.request_access.views import (
    AccessRequestConfirmationPage,
    DatasetAccessRequest,
    ToolsAccessRequestPart1,
    ToolsAccessRequestPart2,
    ToolsAccessRequestPart3,
)

urlpatterns = [
    path('', login_required(DatasetAccessRequest.as_view()), name='index',),
    path(
        '<uuid:dataset_uuid>',
        login_required(DatasetAccessRequest.as_view()),
        name='dataset',
    ),
    path(
        '<int:pk>/tools-1',
        login_required(ToolsAccessRequestPart1.as_view()),
        name='tools-1',
    ),
    path(
        '<int:pk>/tools-2',
        login_required(ToolsAccessRequestPart2.as_view()),
        name='tools-2',
    ),
    path(
        '<int:pk>/tools-3',
        login_required(ToolsAccessRequestPart3.as_view()),
        name='tools-3',
    ),
    path(
        '<int:pk>/confirmation',
        login_required(AccessRequestConfirmationPage.as_view()),
        name='confirmation-page',
    ),
]
