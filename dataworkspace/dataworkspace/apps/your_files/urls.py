from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.your_files.views import (
    CreateTableDAGStatusView,
    CreateTableFailedView,
    CreateTableIngestingView,
    CreateTableSuccessView,
    CreateTableValidatingView,
    CreateTableView,
    file_browser_html_view,
)

urlpatterns = [
    path('', login_required(file_browser_html_view), name='files'),
    path(
        'create-table', login_required(CreateTableView.as_view()), name='create-table'
    ),
    path(
        'create-table/validating',
        login_required(CreateTableValidatingView.as_view()),
        name='create-table-validating',
    ),
    path(
        'create-table/ingesting',
        login_required(CreateTableIngestingView.as_view()),
        name='create-table-ingesting',
    ),
    path(
        'create-table/success',
        login_required(CreateTableSuccessView.as_view()),
        name='create-table-success',
    ),
    path(
        'create-table/failed',
        login_required(CreateTableFailedView.as_view()),
        name='create-table-failed',
    ),
    path(
        'create-table/status/<str:execution_date>',
        login_required(CreateTableDAGStatusView.as_view()),
        name='create-table-status',
    ),
]
