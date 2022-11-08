from django.db import transaction, IntegrityError
from django.contrib import messages
from django.http import Http404
from django.views.generic import DetailView
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect, render, reverse

from dataworkspace.apps.data_collections.forms import SelectCollectionForMembershipForm
from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionVisualisationCatalogueItemMembership,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event


def get_authorised_collections(request):
    collections = Collection.objects.live()
    if request.user.is_superuser:
        return collections
    return collections.filter(owner=request.user)


def get_authorised_collection(request, collection_id):
    return get_object_or_404(get_authorised_collections(request), id=collection_id)


class CollectionsDetailView(DetailView):
    template_name = "data_collections/collection_detail.html"

    def get_object(self, queryset=None):
        return get_authorised_collection(self.request, self.kwargs["collections_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source_object = self.get_object()
        context["source_object"] = source_object
        context["dataset_collections"] = source_object.dataset_collections.filter(
            deleted=False
        ).order_by("dataset__name")
        context["visualisation_collections"] = source_object.visualisation_collections.filter(
            deleted=False
        ).order_by("visualisation__name")

        return context


@require_http_methods(["GET"])
def dataset_membership_confirm_removal(request, collections_id, data_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = CollectionDatasetMembership.objects.get(id=data_membership_id)
    # The membership ID doesn't match the collection ID in the URL
    if membership.collection.id != collection.id:
        raise Http404

    context = {
        "collection": collection.name,
        "collection_url": reverse(
            "data_collections:collections_view",
            kwargs={
                "collections_id": collection.id,
            },
        ),
        "item_name": membership.dataset.name,
        "action_url": reverse(
            "data_collections:collection_data_membership",
            kwargs={
                "collections_id": collection.id,
                "data_membership_id": membership.id,
            },
        ),
    }
    return render(request, "data_collections/collection_membership_confirm_removal.html", context)


@require_http_methods(["GET"])
def visualisation_membership_confirm_removal(request, collections_id, visualisation_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = CollectionVisualisationCatalogueItemMembership.objects.get(
        id=visualisation_membership_id
    )
    # The membership ID doesn't match the collection ID in the URL
    if membership.collection.id != collection.id:
        raise Http404

    context = {
        "collection_name": collection.name,
        "collection_url": reverse(
            "data_collections:collections_view",
            kwargs={
                "collections_id": collection.id,
            },
        ),
        "item_name": membership.visualisation.name,
        "action_url": reverse(
            "data_collections:collection_visualisation_membership",
            kwargs={
                "collections_id": collection.id,
                "visualisation_membership_id": membership.id,
            },
        ),
    }
    return render(request, "data_collections/collection_membership_confirm_removal.html", context)


@require_http_methods(["POST"])
def delete_datasets_membership(request, collections_id, data_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = CollectionDatasetMembership.objects.get(id=data_membership_id)

    # The membership ID doesn't match the collection ID in the URL
    if membership.collection.id != collection.id:
        raise Http404

    membership.delete(request.user)
    messages.success(request, f"{membership.dataset.name} has been removed from this collection.")

    return redirect("data_collections:collections_view", collections_id=collections_id)


@require_http_methods(["POST"])
def delete_visualisation_membership(request, collections_id, visualisation_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = CollectionVisualisationCatalogueItemMembership.objects.get(
        id=visualisation_membership_id
    )

    # The membership ID doesn't match the collection ID in the URL
    if membership.collection.id != collection.id:
        raise Http404

    membership.delete(request.user)
    messages.success(
        request, f"{membership.visualisation.name} has been removed from this collection."
    )

    return redirect("data_collections:collections_view", collections_id=collections_id)


@require_http_methods(["GET", "POST"])
def select_collection_for_membership(
    request, dataset_class, membership_model_class, membership_model_relationship_name, dataset_id
):
    dataset = get_object_or_404(dataset_class.objects.live().filter(published=True), pk=dataset_id)
    user_collections = get_authorised_collections(request)
    if request.method == "POST":
        form = SelectCollectionForMembershipForm(
            request.POST,
            user_collections=user_collections,
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    membership_model_class.objects.create(
                        collection=user_collections.get(pk=form.cleaned_data["collection"]),
                        created_by=request.user,
                        **{membership_model_relationship_name: dataset},
                    )
            except IntegrityError:
                messages.success(request, f"{dataset.name} was already in this collection")
            else:
                messages.success(request, f"{dataset.name} has been added to this collection.")

            log_event(
                request.user,
                EventLog.TYPE_ADD_DATASET_TO_COLLECTION,
                related_object=dataset,
            )

            return redirect(
                "data_collections:collections_view", collections_id=form.cleaned_data["collection"]
            )
    else:
        form = SelectCollectionForMembershipForm(user_collections=user_collections)

    return render(
        request,
        "data_collections/select_collection_for_membership.html",
        {
            "dataset": dataset,
            "form": form,
        },
    )
