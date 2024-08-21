from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.add_table.views import (
    AddTableView,
    TableNameView,
    TableSchemaView,
    ClassificationCheckView,
    DescriptiveNameView,
    UploadCSVView,
    AddTableDataTypesView,
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
        "<str:schema>/classification-check",
        login_required(ClassificationCheckView.as_view()),
        name="classification-check",
    ),
    path(
        "<str:schema>/descriptive-name",
        login_required(DescriptiveNameView.as_view()),
        name="descriptive-name",
    ),
    path(
        "<str:schema>/<str:descriptive_name>/table-name",
        login_required(TableNameView.as_view()),
        name="table-name",
    ),
    path(
        "<str:schema>/<str:descriptive_name>/<str:table_name>/upload-csv",
        login_required(UploadCSVView.as_view()),
        name="upload-csv",
    ),
    path(
        "<str:schema>/<str:descriptive_name>/<str:table_name>/<file_name>",
        login_required(AddTableDataTypesView.as_view()),
        name="data-types",
    ),
]
