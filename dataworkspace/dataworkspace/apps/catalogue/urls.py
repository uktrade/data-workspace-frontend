from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.catalogue.views import (
    ReferenceDatasetDetailView,
    datagroup_item_view,
    dataset_full_path_view,
)

urlpatterns = [
    # Old redirect URLs
    path("<str:slug>", login_required(datagroup_item_view), name="datagroup_item"),
    path(
        "<str:group_slug>/<str:set_slug>",
        login_required(dataset_full_path_view),
        name="dataset_fullpath",
    ),
    path(
        "<str:group_slug>/reference/<str:reference_slug>",
        login_required(ReferenceDatasetDetailView.as_view()),
        name="reference_dataset",
    ),
]
