from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.add_table.views import (
    AddTableView,
    TableSchemaView,
    UploadClassificationCheckView,
)


urlpatterns = [
    path(
        "",
        login_required(AddTableView.as_view()),
        name="add-table",
    ),
    path(
        "table-schema",
        login_required(TableSchemaView.as_view()),
        name="table-schema",
    ),
     path(
        "classification-check",
        login_required(UploadClassificationCheckView.as_view()),
        name="classification-check",
    ),
]
