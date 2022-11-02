from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.data_collections import views

urlpatterns = [
    path(
        "<uuid:collections_id>",
        login_required(views.CollectionsDetailView.as_view()),
        name="collections_view",
    ),
    path(
        "<uuid:collections_id>/dataset-memberships/<int:data_membership_id>",
        login_required(views.delete_datasets_membership),
        name="collection_data_membership",
    ),
    path(
        "<uuid:collections_id>/visualisations-memberships/<int:visualisation_membership_id>",
        login_required(views.delete_visualisation_membership),
        name="collection_visualisation_membership",
    ),
]
