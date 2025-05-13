import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import resolve, reverse
from django.views.generic import CreateView, DetailView, FormView, UpdateView

from dataworkspace import zendesk
from dataworkspace.apps.accounts.models import Profile
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.utils import is_user_email_domain_valid
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.request_access import models
from dataworkspace.apps.request_access.forms import (  # pylint: disable=import-error
    DatasetAccessRequestForm,
    SelfCertifyForm,
    StataAccessForm,
    ToolsAccessRequestForm,
)
from dataworkspace.notify import EmailSendFailureException, send_email

logger = logging.getLogger("app")


class DatasetAccessRequest(CreateView):
    model = models.AccessRequest
    template_name = "request_access/dataset.html"
    form_class = DatasetAccessRequestForm

    def get_initial(self):
        return {"contact_email": self.request.user.email}

    def get_context_data(self, **kwargs):
        user_has_tools_access = self.request.user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()
        catalogue_item = find_dataset(self.kwargs["dataset_uuid"], self.request.user)
        context = super().get_context_data(**kwargs)
        context["catalogue_item"] = catalogue_item
        context["is_visualisation"] = isinstance(catalogue_item, VisualisationCatalogueItem)
        context["user_has_tools_access"] = user_has_tools_access
        context["eligibility_criteria_not_met"] = (
            resolve(self.request.path_info).url_name == "eligibility_criteria_not_met"
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        user_has_tools_access = request.user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()
        user_has_dataset_access = False
        # requesting dataset
        if "dataset_uuid" in self.kwargs:
            catalogue_item = find_dataset(self.kwargs["dataset_uuid"], request.user)
            user_has_dataset_access = (
                catalogue_item.user_has_access(self.request.user)
                if catalogue_item.type != DataSetType.REFERENCE
                else None
            )
            # already has access to dataset
            if user_has_dataset_access:
                return HttpResponseRedirect(
                    reverse(
                        "datasets:dataset_detail",
                        kwargs={"dataset_uuid": self.kwargs["dataset_uuid"]},
                    )
                )
        else:
            # requesting tools
            if not user_has_tools_access:
                access_request = models.AccessRequest.objects.create(
                    requester=self.request.user,
                    catalogue_item_id=catalogue_item.id if catalogue_item else None,
                )
                return HttpResponseRedirect(
                    reverse("request-access:tools", kwargs={"pk": access_request.pk})
                )
            # already has access to tools
            elif user_has_tools_access:
                return render(request, "request_access/you_have_access.html")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user_has_tools_access = self.request.user.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()
        catalogue_item = find_dataset(self.kwargs["dataset_uuid"], self.request.user)

        access_request = models.AccessRequest.objects.create(
            requester=self.request.user,
            catalogue_item_id=catalogue_item.id,
            contact_email=form.cleaned_data["contact_email"],
            reason_for_access=form.cleaned_data["reason_for_access"],
            data_access_status="waiting",
            eligibility_criteria_met=resolve(self.request.path_info).url_name
            != "eligibility_criteria_not_met",
        )

        if user_has_tools_access or catalogue_item.type in [
            DataSetType.VISUALISATION,
            DataSetType.DATACUT,
            DataSetType.MASTER,
        ]:
            return HttpResponseRedirect(
                reverse("request-access:summary-page", kwargs={"pk": access_request.pk})
            )

        return HttpResponseRedirect(
            reverse("request-access:tools", kwargs={"pk": access_request.pk})
        )


class RequestAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        access_request = self.get_object()
        if access_request.requester != request.user:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class DatasetAccessRequestUpdate(RequestAccessMixin, UpdateView):
    model = models.AccessRequest
    template_name = "request_access/dataset.html"
    form_class = DatasetAccessRequestForm

    def get_success_url(self):
        if self.object.journey == self.object.JOURNEY_DATASET_ACCESS:
            return reverse("request-access:summary-page", kwargs={"pk": self.object.pk})
        return reverse("request-access:tools", kwargs={"pk": self.object.pk})


class ToolsAccessRequest(RequestAccessMixin, UpdateView):
    model = models.AccessRequest
    template_name = "request_access/tools.html"
    form_class = ToolsAccessRequestForm

    def get_success_url(self):
        return reverse("request-access:summary-page", kwargs={"pk": self.object.pk})


class AccessRequestSummaryPage(RequestAccessMixin, DetailView):
    model = models.AccessRequest
    template_name = "request_access/summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["catalogue_item"] = (
            find_dataset(ctx["object"].catalogue_item_id, self.request.user)
            if ctx["object"].catalogue_item_id
            else None
        )
        return ctx

    def post(self, request, pk):
        return HttpResponseRedirect(reverse("request-access:confirmation-page", kwargs={"pk": pk}))


class AccessRequestConfirmationPage(RequestAccessMixin, DetailView):
    model = models.AccessRequest
    template_name = "request_access/confirmation-page.html"

    def send_notification_email(self, email, name_dataset, url_dataset):

        logger.info(
            "send_notification_email: Sending email notification to %s for Dataset access request",
            email,
        )

        try:
            send_email(
                template_id=settings.NOTIFY_DATASET_NOTIFICATIONS_USER_ACCESS_TEMPLATE_ID,
                email_address=email,
                personalisation={
                    "dataset_name": name_dataset,
                    "dataset_url": url_dataset,
                },
            )
        except EmailSendFailureException as e:
            logger.exception("Failed to send email")
            logger.exception("Failed to send email %s", e)

        else:
            logger.info(
                "send_notification_email: for %s is set",
                email,
            )
        logger.info("send_notification_email: Stop")

    def get(self, request, *args, **kwargs):
        access_request = self.get_object()
        catalogue_item = (
            find_dataset(access_request.catalogue_item_id, self.request.user)
            if access_request.catalogue_item_id
            else None
        )
        name_dataset = catalogue_item.name
        url_dataset = request.build_absolute_uri(catalogue_item.get_absolute_url())
        # In Dev Ignore the API call to Zendesk and notify
        if settings.ENVIRONMENT == "Dev":
            access_request.zendesk_reference_number = "Test"
            access_request.save()
            return super().get(request, *args, **kwargs)

        if not access_request.zendesk_reference_number:
            if isinstance(catalogue_item, (DataSet, VisualisationCatalogueItem)):
                access_request.zendesk_reference_number = zendesk.notify_dataset_access_request(
                    request,
                    access_request,
                    catalogue_item,
                )
                self.send_notification_email(
                    access_request.requester.email, name_dataset, url_dataset
                )
            else:
                access_request.zendesk_reference_number = zendesk.create_zendesk_ticket(
                    request,
                    access_request,
                    catalogue_item,
                )
            access_request.save()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["catalogue_item"] = (
            find_dataset(self.object.catalogue_item_id, self.request.user)
            if self.object.catalogue_item_id
            else None
        )
        return context


class SelfCertifyView(FormView):
    form_class = SelfCertifyForm
    template_name = "request_access/self-certify.html"

    def get(self, request, *args, **kwargs):
        if not is_user_email_domain_valid(request.user.email):
            return HttpResponseRedirect(reverse("request-access:index"))
        return super().get(request, args, kwargs)

    def form_valid(self, form):
        certificate_date = form.cleaned_data["certificate_date"]
        user_id = self.request.user.id
        user_profile = Profile.objects.get(user_id=user_id)

        user_profile.tools_certification_date = certificate_date
        user_profile.is_renewal_email_sent = False
        user_profile.save()

        user = get_user_model().objects.get(id=user_id)

        permission_codenames = [
            "start_all_applications",
            "access_quicksight",
        ]
        content_type = ContentType.objects.get_for_model(ApplicationInstance)
        permissions = Permission.objects.filter(
            codename__in=permission_codenames,
            content_type=content_type,
        )

        for permission in permissions:
            user.user_permissions.add(permission)

        user.save()

        return HttpResponseRedirect("/tools?access=true")


class StataAccessRequest(CreateView):
    model = models.AccessRequest
    template_name = "request_access/stata_request_access.html"
    form_class = StataAccessForm

    def dispatch(self, request, *args, **kwargs):
        access_request = models.AccessRequest.objects.create(
            requester=self.request.user,
        )

        return HttpResponseRedirect(
            reverse("request-access:stata-access-page", kwargs={"pk": access_request.pk})
        )


class StataAccessView(FormView):
    form_class = StataAccessForm
    template_name = "request_access/stata_request_access.html"

    def form_valid(self, form):
        reason_for_spss_and_stata = form.cleaned_data["reason_for_spss_and_stata"]

        self.request.session["reason_for_spss_and_stata"] = reason_for_spss_and_stata

        return HttpResponseRedirect(
            reverse("request-access:confirmation-page", kwargs={"pk": self.kwargs["pk"]})
        )
