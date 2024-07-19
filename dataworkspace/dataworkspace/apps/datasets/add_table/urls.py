from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.add_table.views import (
    AddTableView, TableSchemaView,
)


urlpatterns = [
    path(
        "",
        login_required(AddTableView.as_view()),
        name="add-table",
    ),
    path(
        "table_schema",
        login_required(TableSchemaView.as_view()),
        name="table-schema",
    ),
]
