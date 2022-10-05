from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse
from django.views.generic import TemplateView, UpdateView, DetailView

from dataworkspace.apps.request_data.forms import (  # pylint: disable=import-error
    RequestDataWhoAreYouForm,
    RequestDataDescriptionForm,
    RequestDataPurposeForm,
    RequestDataSecurityClassificationForm,
    RequestDataLocationForm,
    RequestDataOwnerOrManagerForm,
    RequestDataLicenceForm,
)
from dataworkspace.apps.request_data.models import (  # pylint: disable=import-error
    DataRequest,
    RoleType,
    DataRequestStatus,
)
from dataworkspace.help_desk import create_support_request  # pylint: disable=import-error


class RequestData(TemplateView):
    template_name = "request_data/index.html"

    def post(self, request):
        data_request = DataRequest.objects.create(requester=request.user)
        return HttpResponseRedirect(
            reverse("request-data:who-are-you", kwargs={"pk": data_request.pk})
        )


class RequestDataWhoAreYou(UpdateView):
    model = DataRequest
    template_name = "request_data/who-are-you.html"
    form_class = RequestDataWhoAreYouForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse("request-data:index")

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            if (
                self.object.requester_role not in {RoleType.IAM, RoleType.IAO}
                and not self.object.name_of_owner_or_manager
            ):
                return (
                    reverse("request-data:owner-or-manager", kwargs={"pk": self.object.pk})
                    + "?change"
                )

            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        if self.object.requester_role in {RoleType.IAM, RoleType.IAO}:
            return reverse("request-data:describe-data", kwargs={"pk": self.object.pk})

        return reverse("request-data:owner-or-manager", kwargs={"pk": self.object.pk})


class RequestDataOwnerOrManager(UpdateView):
    model = DataRequest
    template_name = "request_data/data-owner-or-manager.html"
    form_class = RequestDataOwnerOrManagerForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:who-are-you", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        return reverse("request-data:describe-data", kwargs={"pk": self.object.pk})


class RequestDataDescription(UpdateView):
    model = DataRequest
    template_name = "request_data/data-description.html"
    form_class = RequestDataDescriptionForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        elif self.object.requester_role in {RoleType.IAM, RoleType.IAO}:
            context["backlink"] = reverse(
                "request-data:who-are-you", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:owner-or-manager", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        return reverse("request-data:purpose-of-data", kwargs={"pk": self.object.pk})


class RequestDataPurpose(UpdateView):
    model = DataRequest
    template_name = "request_data/data-purpose.html"
    form_class = RequestDataPurposeForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:describe-data", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        return reverse("request-data:security-classification", kwargs={"pk": self.object.pk})


class RequestDataSecurityClassification(UpdateView):
    model = DataRequest
    template_name = "request_data/security-classification.html"
    form_class = RequestDataSecurityClassificationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:purpose-of-data", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        return reverse("request-data:location-of-data", kwargs={"pk": self.object.pk})


class RequestDataLocation(UpdateView):
    model = DataRequest
    template_name = "request_data/data-location.html"
    form_class = RequestDataLocationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:licence-of-data", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        if "change" in self.request.GET:
            return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})

        return reverse("request-data:licence-of-data", kwargs={"pk": self.object.pk})


class RequestDataLicence(UpdateView):
    model = DataRequest
    template_name = "request_data/data-licence.html"
    form_class = RequestDataLicenceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "change" in self.request.GET:
            context["backlink"] = reverse(
                "request-data:check-answers", kwargs={"pk": self.object.pk}
            )
        else:
            context["backlink"] = reverse(
                "request-data:security-classification", kwargs={"pk": self.object.pk}
            )

        return context

    def get_success_url(self):
        return reverse("request-data:check-answers", kwargs={"pk": self.object.pk})


class RequestDataCheckAnswers(DetailView):
    model = DataRequest
    template_name = "request_data/check-answers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["backlink"] = reverse(
            "request-data:location-of-data", kwargs={"pk": self.object.pk}
        )
        context["show_owner_or_manager"] = self.object.requester_role not in {
            RoleType.IAM,
            RoleType.IAO,
        }

        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status != DataRequestStatus.draft:
            return HttpResponseRedirect(
                reverse("request-data:confirmation-page", kwargs={"pk": obj.pk})
            )

        # If they've hacked the URL, some required fields might be blank.
        try:
            obj.clean_fields(exclude=["help_desk_ticket_id"])
        except ValidationError:
            return HttpResponseBadRequest()

        help_desk_message = f"""
A request for a new dataset on Data Workspace has been submitted. Here are the details:

# Request details

## Who they are in relation to the request
{obj.get_requester_role_display()}

## (Alternative) name of IAO/IAM
{obj.name_of_owner_or_manager or '[not provided]'}

## Description of the data
{obj.data_description or '[not provided]'}

## Purpose of the data
{obj.data_purpose or '[not provided]'}

## Location of the data
{obj.data_location or '[not provided]'}

## Security classification
{obj.get_security_classification_display() or '[not provided]'}

## Licence of the data
{obj.data_licence or '[not provided]'}

# Personal details

## Full name
{obj.requester.get_full_name()}

## Email address
{obj.requester.email}
"""

        from django.conf import settings

        print("settings:::", flush=True)
        print(settings.HELP_DESK_INTERFACE, flush=True)

        ticket_id = create_support_request(
            obj.requester,
            obj.requester.email,
            help_desk_message,
            tag="request-for-data",
            subject="Request for new dataset on Data Workspace",
        )

        obj.status = DataRequestStatus.submitted
        obj.help_desk_ticket_id = ticket_id
        obj.save()

        return HttpResponseRedirect(
            reverse("request-data:confirmation-page", kwargs={"pk": obj.pk})
        )


class RequestDataConfirmationPage(DetailView):
    model = DataRequest
    template_name = "request_data/confirmation-page.html"
