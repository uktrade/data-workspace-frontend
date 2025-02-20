from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.your_files.views import (
    CreateSchemaView,
    CreateTableAppendingToTableView,
    CreateTableConfirmDataTypesView,
    CreateTableConfirmNameView,
    CreateTableConfirmSchemaView,
    CreateTableCreatingTableView,
    CreateTableFailedView,
    CreateTableIngestingView,
    CreateTableRenamingTableView,
    CreateTableSuccessView,
    CreateTableTableExists,
    CreateTableValidatingView,
    CreateTableView,
    RestoreTableView,
    RestoreTableViewFailed,
    RestoreTableViewInProgress,
    RestoreTableViewSuccess,
    UploadedTableListView,
    your_files_home,
)

urlpatterns = [
    path(
        "create-table/confirm",
        login_required(CreateTableView.as_view()),
        name="create-table-confirm",
    ),
    path(
        "create-table/confirm-schema",
        login_required(CreateTableConfirmSchemaView.as_view()),
        name="create-table-confirm-schema",
    ),
    path(
        "create-schema/",
        login_required(CreateSchemaView.as_view()),
        name="create-schema",
    ),
    path(
        "create-table/confirm-name",
        login_required(CreateTableConfirmNameView.as_view()),
        name="create-table-confirm-name",
    ),
    path(
        "create-table/confirm-data-types",
        login_required(CreateTableConfirmDataTypesView.as_view()),
        name="create-table-confirm-data-types",
    ),
    path(
        "create-table/validating",
        login_required(CreateTableValidatingView.as_view()),
        name="create-table-validating",
    ),
    path(
        "create-table/creating-table",
        login_required(CreateTableCreatingTableView.as_view()),
        name="create-table-creating-table",
    ),
    path(
        "create-table/ingesting",
        login_required(CreateTableIngestingView.as_view()),
        name="create-table-ingesting",
    ),
    path(
        "create-table/renaming-table",
        login_required(CreateTableRenamingTableView.as_view()),
        name="create-table-renaming-table",
    ),
    path(
        "create-table/appending",
        login_required(CreateTableAppendingToTableView.as_view()),
        name="create-table-appending",
    ),
    path(
        "create-table/success",
        login_required(CreateTableSuccessView.as_view()),
        name="create-table-success",
    ),
    path(
        "create-table/failed",
        login_required(CreateTableFailedView.as_view()),
        name="create-table-failed",
    ),
    path(
        "uploaded-tables",
        login_required(UploadedTableListView.as_view()),
        name="uploaded-tables",
    ),
    path(
        "restore-table/<int:pk>/",
        login_required(RestoreTableView.as_view()),
        name="restore-table",
    ),
    path(
        "restore-table/<int:pk>/in-progress",
        login_required(RestoreTableViewInProgress.as_view()),
        name="restore-table-in-progress",
    ),
    path(
        "restore-table/<int:pk>/failed",
        login_required(RestoreTableViewFailed.as_view()),
        name="restore-table-failed",
    ),
    path(
        "create-table/table-exists",
        login_required(CreateTableTableExists.as_view()),
        name="create-table-table-exists",
    ),
    path(
        "restore-table/<int:pk>/success",
        login_required(RestoreTableViewSuccess.as_view()),
        name="restore-table-success",
    ),
    path("", login_required(your_files_home), name="files"),
    path("<path:s3_path>", login_required(your_files_home), name="files"),
]
