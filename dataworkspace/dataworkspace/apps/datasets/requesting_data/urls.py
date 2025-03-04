from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.requesting_data.views import DatasetDescriptionsView, DatasetNameView

urlpatterns = [

    path(
        "dataset-name",
        login_required(DatasetNameView.as_view()),
        name="dataset-name",
    ),
    path(
        "dataset-descriptions",
        login_required(DatasetDescriptionsView.as_view()),
        name="dataset-descriptions",
    ),

]
