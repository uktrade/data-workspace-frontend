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
    path(
        "<uuid:collections_id>/users/<int:user_membership_id>/delete",
        login_required(views.remove_user_membership),
        name="remove-user",
    ),
    path(
        "<uuid:collections_id>/notes/edit",
        login_required(views.CollectionNotesView.as_view()),
        name="collection-notes",
    ),
    path(
        "<uuid:collections_id>/edit",
        login_required(views.CollectionEditView.as_view()),
        name="collection-edit",
    ),
    path(
        "create",
        login_required(views.CollectionCreateView.as_view()),
        name="collection-create",
    ),
    path("", login_required(views.CollectionListView.as_view()), name="collections-list"),
    path(
        "<uuid:collections_id>/delete",
        login_required(views.remove_collection_confirmation),
        name="remove-collection-confirmation",
    ),
    path(
        "<uuid:collections_id>/delete-confirmed",
        login_required(views.remove_collection),
        name="remove-collection",
    ),
    path(
        "create/dataset/<uuid:dataset_id>",
        login_required(views.CollectionCreateView.as_view()),
        {
            "dataset_class": DataSet,
            "membership_model_class": CollectionDatasetMembership,
            "membership_model_relationship_name": "dataset",
        },
        name="collection-create-with-selected-dataset",
    ),
    path(
        "create/visualisation/<uuid:dataset_id>",
        login_required(views.CollectionCreateView.as_view()),
        {
            "dataset_class": VisualisationCatalogueItem,
            "membership_model_class": CollectionVisualisationCatalogueItemMembership,
            "membership_model_relationship_name": "visualisation",
        },
        name="collection-create-with-selected-visualisation",
    ),
    path(
        "<uuid:collections_id>/history",
        login_required(views.history_of_collection_changes),
        name="history-of-collection-changes",
    ),
    path(
        "<uuid:collections_id>/request_collection_access",
        login_required(views.RequestAccessToCollection.as_view()),
        name="request_collection_access",
    ),
    path(
        "<uuid:collections_id>/request_collection_complete",
        login_required(views.request_collection_complete),
        name="request_collection_complete",
    ),
]
