from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.add_table.views import (
    AddTableView,
    TableSchemaView,
    ClassificationCheck,
    DescriptiveNameView,
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
        login_required(ClassificationCheck.as_view()),
        name="classification-check",
    ),
    path(
        "<str:schema>/descriptive-name",
        login_required(DescriptiveNameView.as_view()),
        name="descriptive-name",
    ),

]
