import logging

from csp.decorators import csp_update
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from dataworkspace.apps.data_collections.forms import (
    CollectionEditForm,
    CollectionNotesForm,
    CollectionUserAddForm,
    RequestAccessToCollectionForm,
    SelectCollectionForMembershipForm,
)
from dataworkspace.apps.data_collections.models import (
    Collection,
    CollectionDatasetMembership,
    CollectionUserAccessType,
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
    collections = Collection.objects.all().order_by("name")
    return (
        collections.filter(
            Q(owner=request.user)
            | Q(
                Q(user_access_type=CollectionUserAccessType.REQUIRES_AUTHORIZATION)
                & Q(user_memberships__user=request.user, user_memberships__deleted=False)
            )
            | Q(user_access_type=CollectionUserAccessType.REQUIRES_AUTHENTICATION)
        )
        .order_by("name")
        .distinct()
    )


def get_only_live_authorised_collections(request):
    collections = Collection.objects.live().order_by("name")
    return (
        collections.filter(
            Q(owner=request.user)
            | Q(
                Q(user_access_type=CollectionUserAccessType.REQUIRES_AUTHORIZATION)
                & Q(user_memberships__user=request.user, user_memberships__deleted=False)
            )
            | Q(user_access_type=CollectionUserAccessType.REQUIRES_AUTHENTICATION)
        )
        .order_by("name")
        .distinct()
    )


def get_editable_live_authorised_collections(request):
    # Only admins or the collection owner can edit an "OPEN" collection
    live_collections = get_only_live_authorised_collections(request)
    if request.user.is_superuser:
        return live_collections
    return live_collections.filter(owner=request.user)


def get_authorised_collection(request, collection_id):
    return get_object_or_404(get_authorised_collections(request), id=collection_id)


def get_authorised_collections_or_return_none(request, collection_id):
    try:
        return get_authorised_collections(request).get(id=collection_id)
    except Collection.DoesNotExist:
        return None


class CollectionsDetailView(DetailView):
    template_name = "data_collections/collection_detail.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.object = None

    def get_queryset(self):
        return get_authorised_collections(self.request)

    def get_object(self, queryset=None):
        return get_authorised_collections_or_return_none(
            self.request, self.kwargs["collections_id"]
        )

    @csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC, STYLE_SRC=settings.WEBPACK_SCRIPT_SRC)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

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
                Prefetch(
                    "dataset__tags",
                    queryset=Tag.objects.filter(type=TagType.PUBLISHER),
                    to_attr="publishers",
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
                Prefetch(
                    "visualisation__tags",
                    queryset=Tag.objects.filter(type=TagType.PUBLISHER),
                    to_attr="publishers",
                ),
            )
            .order_by("visualisation__name")
        )
        context["user_memberships"] = source_object.user_memberships.live().order_by(
            "user__first_name", "user__last_name"
        )

        collection_user_ids = ([source_object.owner.id] if source_object.owner else []) + [
            membership.user.id
            for membership in source_object.user_memberships.filter(deleted=False)
        ]
        number_of_user_ids = len(set(collection_user_ids))
        context["personal_collection"] = (
            number_of_user_ids == 1 and source_object.owner == self.request.user
        )

        context["shared_collection"] = (
            number_of_user_ids > 1 and self.request.user.id in collection_user_ids
        )
        context["collection_for_all"] = (
            source_object.user_access_type == "REQUIRES_AUTHENTICATION"
            and self.request.user.id not in collection_user_ids
        )

        log_event(
            self.request.user,
            EventLog.TYPE_COLLECTION_VIEW,
            source_object,
        )

        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object:
            return redirect(
                "data_collections:request_collection_access",
                collections_id=self.kwargs["collections_id"],
            )
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


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
    user_collections = get_editable_live_authorised_collections(request)

    if request.method == "POST":
        form = SelectCollectionForMembershipForm(
            request.POST,
            user_collections=user_collections,
        )
        if form.is_valid():
            if form.cleaned_data["collection"] == "add_to_new_collection":
                if membership_model_relationship_name == "dataset":
                    return redirect(
                        "data_collections:collection-create-with-selected-dataset",
                        dataset_id=dataset.id,
                    )
                elif membership_model_relationship_name == "visualisation":
                    return redirect(
                        "data_collections:collection-create-with-selected-visualisation",
                        dataset_id=dataset.id,
                    )

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
                (
                    EventLog.TYPE_ADD_VISUALISATION_TO_COLLECTION
                    if dataset.type == DataSetType.VISUALISATION
                    else EventLog.TYPE_ADD_DATASET_TO_COLLECTION
                ),
                related_object=user_collections.get(pk=form.cleaned_data["collection"]),
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
            "collection_url": (
                reverse(
                    "data_collections:collection-create-with-selected-dataset", args=(dataset.id,)
                )
                if membership_model_relationship_name == "dataset"
                else reverse(
                    "data_collections:collection-create-with-selected-visualisation",
                    args=(dataset.id,),
                )
            ),
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
                    user=get_user_model().objects.get(
                        email=form.cleaned_data["email"]
                    ).first().profile.sso_status== "active",
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
    try:
        send_email(
            template_id=settings.NOTIFY_COLLECTIONS_NOTIFICATION_USER_REMOVED_ID,
            email_address=membership.user.email,
            personalisation={
                "collection_name": collection.name,
                "user_name": request.user.get_full_name(),
            },
        )
    except EmailSendFailureException:
        logger.exception("Failed to send email")

    return redirect("data_collections:collection-users", collections_id=collections_id)


class CollectionNotesView(UpdateView):
    model = Collection
    form_class = CollectionNotesForm
    template_name = "data_collections/collection_notes.html"
    context_object_name = "collection"

    @csp_update(SCRIPT_SRC=settings.WEBPACK_SCRIPT_SRC, STYLE_SRC=settings.WEBPACK_SCRIPT_SRC)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_object(self, queryset=None):
        return get_authorised_collection(self.request, self.kwargs["collections_id"])

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.save(commit=False)
        messages.success(self.request, "The notes have been updated")
        log_event(
            self.request.user,
            EventLog.TYPE_EDITED_COLLECTION_NOTES,
            related_object=form.instance,
        )
        return super().form_valid(form)


class CollectionEditView(UpdateView):
    model = Collection
    form_class = CollectionEditForm
    template_name = "data_collections/collection_form.html"
    context_object_name = "collection"

    def get_object(self, queryset=None):
        return get_authorised_collection(self.request, self.kwargs["collections_id"])

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.save(commit=False)
        messages.success(self.request, "Your changes have been saved")
        log_event(
            self.request.user,
            EventLog.TYPE_EDITED_COLLECTION,
            related_object=form.instance,
        )
        return super().form_valid(form)


class CollectionCreateView(CreateView):
    model = Collection
    form_class = CollectionEditForm
    template_name = "data_collections/collection_form.html"
    context_object_name = "collection"

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.owner = self.request.user
            form.instance.created_by = self.request.user
            form.save(commit=False)
            log_event(
                self.request.user,
                EventLog.TYPE_CREATED_COLLECTION,
                related_object=form.instance,
            )
            super().form_valid(form)
            if self.kwargs:
                dataset = get_object_or_404(
                    self.kwargs["dataset_class"].objects.live().filter(published=True),
                    pk=self.kwargs["dataset_id"],
                )
                self.kwargs["membership_model_class"].objects.create(
                    collection=form.instance,
                    created_by=self.request.user,
                    **{self.kwargs["membership_model_relationship_name"]: dataset},
                )

        messages.success(self.request, "Your changes have been saved")
        return redirect("data_collections:collections_view", collections_id=form.instance.id)


class CollectionListView(ListView):
    model = Collection
    template_name = "data_collections/collections.html"
    context_object_name = "collections"

    def get_queryset(self):
        return get_only_live_authorised_collections(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        authorised_collections = self.get_queryset()

        personal_collections = []
        shared_collections = []
        collections_for_all = []

        for collection in authorised_collections:
            user_ids = ([collection.owner.id] if collection.owner else []) + [
                membership.user.id
                for membership in collection.user_memberships.filter(deleted=False)
            ]
            number_of_user_ids = len(set(user_ids))
            if number_of_user_ids == 1 and collection.owner == self.request.user:
                personal_collections.append(collection)
            elif number_of_user_ids > 1 and (
                collection.owner == self.request.user or self.request.user.id in user_ids
            ):
                shared_collections.append(collection)
            else:
                collections_for_all.append(collection)

        context["personal_collections"] = personal_collections
        context["shared_collections"] = shared_collections
        context["collections_for_all"] = collections_for_all

        return context


@require_http_methods(["GET"])
def remove_collection_confirmation(request, collections_id):
    collection = get_authorised_collection(request, collections_id)

    context = {
        "collection": collection,
        "action_url": reverse(
            "data_collections:remove-collection",
            kwargs={
                "collections_id": collection.id,
            },
        ),
    }
    return render(request, "data_collections/delete_collection_confirmation_screen.html", context)


@require_http_methods(["POST"])
def remove_collection(request, collections_id):
    collection = get_authorised_collection(request, collections_id)
    if collection.owner == request.user:
        collection.deleted = True
        collection.save()
        messages.success(request, f"{collection.name} collection has been deleted")
    return HttpResponseRedirect(reverse("data_collections:collections-list"))


@require_http_methods(["GET"])
def history_of_collection_changes(request, collections_id):
    collection = get_authorised_collection(request, collections_id)

    collection_history = EventLog.objects.filter(
        ~Q(event_type=EventLog.TYPE_COLLECTION_VIEW),
        object_id=collection.id,
        content_type=ContentType.objects.get_for_model(collection),
    ).order_by("-timestamp")

    context = {
        "collection": collection,
        "collection_history": collection_history,
    }
    return render(request, "data_collections/collection_history.html", context)


class RequestAccessToCollection(FormView):
    form_class = RequestAccessToCollectionForm
    template_name = "data_collections/request_access_to_collection_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["collection"] = Collection.objects.get(id=self.kwargs["collections_id"])
        return context

    def form_valid(self, form):
        try:
            collection = Collection.objects.get(id=self.kwargs["collections_id"])
            send_email(
                template_id=settings.NOTIFY_COLLECTIONS_USER_REQUESTED_ACCESS,
                email_address=collection.owner.email,
                personalisation={
                    "collection_name": collection.name,
                    "collection_url": reverse(
                        "data_collections:collections_view", args=(collection.id,)
                    ),
                    "user_email": form.cleaned_data["email"],
                    "people_url": "https://people.trade.gov.uk/people/get-by-staff-sso-id/{}".format(
                        self.request.user.profile.sso_id
                    ),
                },
            )
        except EmailSendFailureException:
            logger.exception("Failed to send email")
        return HttpResponseRedirect(
            reverse(
                "data_collections:request_collection_complete",
                args=(self.kwargs["collections_id"],),
            )
        )


@require_http_methods(["GET"])
def request_collection_complete(request, collections_id):
    collection = Collection.objects.get(id=collections_id)
    context = {"collection": collection}
    return render(request, "data_collections/request_collection_complete.html", context)
