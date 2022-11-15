from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.data_collections import views
from dataworkspace.apps.data_collections.models import (
    CollectionDatasetMembership,
    CollectionVisualisationCatalogueItemMembership,
)
from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem

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
        "<uuid:collections_id>/dataset-memberships/<int:data_membership_id>/confirm-removal",
        login_required(views.dataset_membership_confirm_removal),
        name="collection_data_membership_confirm_removal",
    ),
    path(
        "<uuid:collections_id>/visualisations-memberships/<int:visualisation_membership_id>",
        login_required(views.delete_visualisation_membership),
        name="collection_visualisation_membership",
    ),
    path(
        "select-collection-for-membership/visualisation/<uuid:dataset_id>",
        login_required(views.select_collection_for_membership),
        {
            "dataset_class": VisualisationCatalogueItem,
            "membership_model_class": CollectionVisualisationCatalogueItemMembership,
            "membership_model_relationship_name": "visualisation",
        },
        name="visualisation_select_collection_for_membership",
    ),
    path(
        "<uuid:collections_id>/visualisations-memberships/<int:visualisation_membership_id>/confirm-removal",
        login_required(views.visualisation_membership_confirm_removal),
        name="collection_visualisation_membership_confirm_removal",
    ),
    path(
        "select-collection-for-membership/dataset/<uuid:dataset_id>",
        login_required(views.select_collection_for_membership),
        {
            "dataset_class": DataSet,
            "membership_model_class": CollectionDatasetMembership,
            "membership_model_relationship_name": "dataset",
        },
        name="dataset_select_collection_for_membership",
    ),
    path(
        "<uuid:collections_id>/users",
        login_required(views.CollectionUsersView.as_view()),
        name="collection-users",
    ),
]
