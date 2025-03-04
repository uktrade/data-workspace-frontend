from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.datasets.requesting_data.views import DatasetDescriptionsView, DatasetNameView, DatasetRestrictionsView

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
        "<uuid:id>/dataset-restrictions",
        login_required(DatasetRestrictionsView.as_view()),
        name="dataset-restrictions",
    ),

]
