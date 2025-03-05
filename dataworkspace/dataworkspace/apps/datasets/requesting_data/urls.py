from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.requesting_data.views import DatasetDescriptionsView, DatasetNameView, DatasetOwnersView, DatasetDataOriginView

urlpatterns = [

    path(
        "dataset-name",
        login_required(DatasetNameView.as_view()),
        name="dataset-name",
    ),
    path(
        "<uuid:id>/dataset-descriptions",
        login_required(DatasetDescriptionsView.as_view()),
        name="dataset-descriptions",
    ),
    path(
        "<uuid:id>/dataset-data-origin",
        login_required(DatasetDataOriginView.as_view()),
        name="dataset-data-origin",
    ),
    path(
        "<uuid:id>/dataset-owners",
        login_required(DatasetOwnersView.as_view()),
        name="dataset-owners",
    ),

]
