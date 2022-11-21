import logging

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.db.models import Prefetch
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect


from django.views.generic import DetailView, FormView
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.conf import settings

from dataworkspace.apps.data_collections.forms import (
    CollectionUserAddForm,
    SelectCollectionForMembershipForm,
)
from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionUserMembership,
    CollectionVisualisationCatalogueItemMembership,
)

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from dataworkspace.apps.datasets.models import Tag
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event
from dataworkspace.notify import EmailSendFailureException, send_email

logger = logging.getLogger("app")


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
        context["dataset_collections"] = (
            source_object.dataset_collections.filter(deleted=False)
            .prefetch_related(
                Prefetch(
                    "dataset__tags",
                    queryset=Tag.objects.filter(type=TagType.SOURCE),
                    to_attr="sources",
                ),
                Prefetch(
                    "dataset__tags",
                    queryset=Tag.objects.filter(type=TagType.TOPIC),
                    to_attr="topics",
                ),
            )
            .order_by("dataset__name")
        )
        context["visualisation_collections"] = (
            source_object.visualisation_collections.filter(deleted=False)
            .prefetch_related(
                Prefetch(
                    "visualisation__tags",
                    queryset=Tag.objects.filter(type=TagType.SOURCE),
                    to_attr="sources",
                ),
                Prefetch(
                    "visualisation__tags",
                    queryset=Tag.objects.filter(type=TagType.TOPIC),
                    to_attr="topics",
                ),
            )
            .order_by("visualisation__name")
        )
        context["user_memberships"] = source_object.user_memberships.live().order_by(
            "user__first_name", "user__last_name"
        )

        return context


@require_http_methods(["GET"])
def dataset_membership_confirm_removal(request, collections_id, data_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = CollectionDatasetMembership.objects.get(id=data_membership_id)
    # The membership ID doesn't match the collection ID in the URL
    if membership.collection.id != collection.id:
        raise Http404

    context = {
        "collection_name": collection.name,
        "collection_id": collection.id,
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
        "collection_id": collection.id,
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
                EventLog.TYPE_ADD_VISUALISATION_TO_COLLECTION
                if dataset.type == DataSetType.VISUALISATION
                else EventLog.TYPE_ADD_DATASET_TO_COLLECTION,
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


class CollectionUsersView(FormView):
    form_class = CollectionUserAddForm
    template_name = "data_collections/collection_users.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collection"] = get_authorised_collection(
            self.request, self.kwargs["collections_id"]
        )
        context["user_memberships"] = (
            context["collection"].user_memberships.live().order_by("user__email")
        )
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["collection"] = get_authorised_collection(
            self.request, self.kwargs["collections_id"]
        )
        return kwargs

    def form_valid(self, form):
        collection = get_authorised_collection(self.request, self.kwargs["collections_id"])
        try:
            with transaction.atomic():
                membership = CollectionUserMembership.objects.create(
                    collection=collection,
                    user=get_user_model().objects.get(email=form.cleaned_data["email"]),
                    created_by=self.request.user,
                )
                log_event(
                    self.request.user,
                    EventLog.TYPE_ADD_USER_TO_COLLECTION,
                    related_object=collection,
                    extra={
                        "added_user": {
                            "id": membership.user.id,
                            "email": membership.user.email,
                            "name": membership.user.get_full_name(),
                        }
                    },
                )
        except IntegrityError:
            messages.success(
                self.request, f"{membership.user.email} already has access to this collection"
            )
        else:
            messages.success(
                self.request,
                f"{membership.user.get_full_name()} has been added to this collection",
            )
            try:
                send_email(
                    template_id=settings.NOTIFY_COLLECTIONS_NOTIFICATION_USER_ADDED_ID,
                    email_address=membership.user.email,
                    personalisation={
                        "collection_name": collection.name,
                        "collection_url": reverse(
                            "data_collections:collections_view", args=(collection.id,)
                        ),
                        "user_name": self.request.user.get_full_name(),
                    },
                )
            except EmailSendFailureException:
                logger.exception("Failed to send email")

        return HttpResponseRedirect(
            reverse("data_collections:collection-users", args=(collection.id,))
        )


@require_http_methods(["POST"])
def remove_user_membership(request, collections_id, user_membership_id):
    collection = get_authorised_collection(request, collections_id)
    membership = get_object_or_404(
        CollectionUserMembership.objects.live(),
        id=user_membership_id,
        collection=collection,
    )

    membership.delete(request.user)
    messages.success(
        request, f"{membership.user.get_full_name()} no longer has access to this collection."
    )

    return redirect("data_collections:collection-users", collections_id=collections_id)
