from django.forms import ValidationError, model_to_dict
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import FormView, TemplateView
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse

from formtools.preview import FormPreview  # pylint: disable=import-error
from formtools.wizard.views import NamedUrlSessionWizardView  # pylint: disable=import-error

from dataworkspace.zendesk import create_support_request
from dataworkspace.apps.datasets.models import DataSet, RequestingDataset
from dataworkspace.apps.datasets.requesting_data.forms import (
    DatasetEnquiriesContactForm,
    DatasetInformationAssetManagerForm,
    DatasetInformationAssetOwnerForm,
    DatasetIntendedAccessForm,
    DatasetNameForm,
    DatasetDescriptionsForm,
    DatasetLicenceForm,
    DatasetPersonalDataForm,
    DatasetRetentionPeriodForm,
    DatasetSecurityClassificationForm,
    DatasetSpecialPersonalDataForm,
    DatasetUpdateFrequencyForm,
    DatasetUserRestrictionsForm,
    SummaryPageForm,
    TrackerPageForm,
)


User = get_user_model()


class AddingCataloguePage(TemplateView):
    template_name = "datasets/requesting_data/adding_data.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incomplete_requests = RequestingDataset.objects.filter(user=self.request.user.id)
        requests = {}
        for request in incomplete_requests:
            progress = 0
            if request.stage_one_complete:
                progress += 1
            if request.stage_two_complete:
                progress += 1
            if request.stage_three_complete:
                progress += 1
            requests[request.name] = {
                "id": request.id,
                "name": request.name,
                "created_date": request.created_date,
                "progress": progress,
                "uuid": request.id,
            }

        previous_page = self.request.META["HTTP_REFERER"]
        if "/requesting-data/adding-catalogue-page" in previous_page:
            context["deleted"] = True
        context["requests"] = requests
        return context


class AddNewCataloguePage(TemplateView):

    template_name = "datasets/requesting_data/add_new_dataset.html"

    def get(self, request):  # pylint: disable=arguments-differ
        previous_page = request.META["HTTP_REFERER"]
        if "/requesting-data/tracker/" in previous_page:
            RequestingDataset.objects.filter(
                id=self.request.session["requesting_catalogue_page"]
            ).delete()
        return render(request, "datasets/requesting_data/add_new_dataset.html")

    def post(self, request, *args, **kwargs):
        requesting_catalogue_page = RequestingDataset.objects.create(name = "Untitled")
        self.kwargs["requesting_catalogue_page_id"] = requesting_catalogue_page.id
        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
            )
        )


class DeleteRequestingCataloguePageJourney(View):
    def get(self, request, requesting_catalogue_page_id):
        dataset = RequestingDataset.objects.filter(id=requesting_catalogue_page_id)
        dataset.delete()
        return HttpResponseRedirect(reverse("adding-catalogue-page"))


class RequestingCataloguePageTrackerView(FormView):
    form_class = TrackerPageForm
    template_name = "datasets/requesting_data/tracker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.kwargs["requesting_catalogue_page_id"]
        )
        self.request.session["requesting_catalogue_page"] = requesting_catalogue_page.id
        context["requesting_catalogue_page_id"] = requesting_catalogue_page.id

        stage_one_complete = requesting_catalogue_page.stage_one_complete
        stage_two_complete = requesting_catalogue_page.stage_two_complete
        stage_three_complete = requesting_catalogue_page.stage_three_complete
        stage_four_complete = requesting_catalogue_page.stage_four_complete
        context["stage_one_complete"] = stage_one_complete
        context["stage_two_complete"] = stage_two_complete
        context["stage_three_complete"] = stage_three_complete
        context["stage_four_complete"] = stage_four_complete

        if (
            stage_one_complete
            and stage_two_complete
            and stage_three_complete
            and stage_four_complete
        ):
            context["all_stages_complete"] = True
        if (
            not stage_one_complete
            and not stage_two_complete
            and not stage_three_complete
            and not stage_four_complete
        ):
            context["backlink"] = reverse("add-new-catalogue-page")
        if "/requesting-data/title-and-description/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-catalogue-page")
        if "/requesting-data/about-this-data/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-catalogue-page")
        if "/requesting-data/access-restrictions/summary" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-catalogue-page")
        if "/requesting-data/adding-catalogue-page" in self.request.META["HTTP_REFERER"]:
            context["backlink"] = reverse("adding-catalogue-page")
        return context

    def form_valid(self, form):
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=form.cleaned_data["requesting_catalogue_page"]
        )
        data_dict = model_to_dict(
            requesting_catalogue_page,
            exclude=[
                "id",
                "tags",
                "user",
                "sensitivity",
                "data_catalogue_editors",
                "stage_one_complete",
                "stage_two_complete",
                "stage_three_complete",
                "stage_four_complete",
            ],
        )
        data_dict["enquiries_contact"] = requesting_catalogue_page.enquiries_contact
        data_dict["information_asset_manager"] = (
            requesting_catalogue_page.information_asset_manager
        )
        data_dict["information_asset_owner"] = requesting_catalogue_page.information_asset_owner
        data_dict["slug"] = requesting_catalogue_page.name.lower().replace(" ", "-")

        dataset = DataSet.objects.create(**data_dict)
        dataset.data_catalogue_editors.set(requesting_catalogue_page.data_catalogue_editors.all())
        dataset.sensitivity.set(requesting_catalogue_page.sensitivity.all())
        dataset.save()

        ticket_id = create_support_request(
            user=self.request.user,
            email=User.objects.get(id=requesting_catalogue_page.user).email,
            message="A new dataset has been requested.",
            tag="data_request",
        )

        RequestingDataset.objects.filter(id=requesting_catalogue_page.id).delete()

        return HttpResponseRedirect(
            reverse(
                "requesting-data-submission",
                kwargs={"ticket_id": ticket_id},
            )
        )


class RequestingCataloguePageBaseWizardView(NamedUrlSessionWizardView, FormPreview):

    user_search_pages = [
        "information-asset-owner",
        "information-asset-manager",
        "enquiries-contact",
    ]

    radio_input_pages = [
        "licence",
        "personal-data",
        "special-personal-data",
        "commercial-sensitive",
        "location-restrictions",
        "network-restrictions",
        "user-restrictions",
    ]

    def add_fields(self, form_list, requesting_catalogue_page, notes_fields=None):
        if notes_fields is None:
            notes_fields = []
        for form in form_list:
            for field in form.cleaned_data:
                if field in notes_fields and form.cleaned_data.get(field):
                    if requesting_catalogue_page.notes:
                        requesting_catalogue_page.notes += (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                    else:
                        requesting_catalogue_page.notes = (
                            f"{form[field].label}\n{form.cleaned_data.get(field)}\n"
                        )
                if field == "sensitivity":
                    requesting_catalogue_page.sensitivity.set(form.cleaned_data.get("sensitivity"))
                else:
                    setattr(requesting_catalogue_page, field, form.cleaned_data.get(field))
            requesting_catalogue_page.save()
        return requesting_catalogue_page

    def get_users(self, search_query):
        email_filter = Q(email__icontains=search_query)
        if len(search_query.split(" ")) > 1:
            name_filter = Q(first_name__icontains=search_query.split()[0]) | Q(
                last_name__icontains=search_query.split(" ")[1]
            )
        else:
            name_filter = Q(first_name__icontains=search_query) | Q(
                last_name__icontains=search_query
            )
        users = User.objects.filter(Q(email_filter | name_filter))

        search_results = []

        for user in users:
            search_results.append(
                {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                }
            )

        return search_results

    def get_template(self, step):
        if step in self.radio_input_pages:
            return "datasets/requesting_data/form_types/radio_input.html"
        if step in "intended-access":
            return "datasets/requesting_data/form_types/radio_input_access.html"
        if step in self.user_search_pages:
            return "datasets/requesting_data/form_types/user_search.html"
        if step == "security-classification":
            return "datasets/requesting_data/form_types/security_classification.html"
        if step == "summary":
            return "datasets/requesting_data/form_types/summary.html"
        else:
            return "datasets/requesting_data/form_types/basic_form.html"

    def get_user_search_context(self, context, step):
        context["form_page"] = step
        context["field"] = step.replace("-", "_")
        try:
            search_query = self.request.GET.dict()["search"]
            if search_query == "":
                raise ValidationError("Please enter a search query.")
            context["search_query"] = search_query
            if search_query:
                context["search_results"] = self.get_users(search_query=search_query.strip())
        except Exception:  # pylint: disable=broad-except
            return context
        return None

    def get_summary_context(self):
        summary_list = []
        questions = {}
        for name, form_item in self.form_list.items():  # pylint: disable=no-member
            for name, field in form_item.base_fields.items():
                questions[name] = field.label
        for step in self.storage.data["step_data"]:
            for key, value in self.get_cleaned_data_for_step(step).items():
                if key == "sensitivity":
                    continue
                if key.replace("_", "-") in self.radio_input_pages and value == "":
                    continue
                if key == "government_security_classification":
                    if value == 1:
                        value = "Official"
                    if value == 2:
                        value = "Official-Sensitive"
                    continue
                summary_list.append(
                    {
                        step: {"question": questions[key], "answer": value},
                    },
                )
        return summary_list

    def get_completed_summary_context(self, requesting_catalogue_page):
        summary_list = []
        questions = {}
        for name, form_item in self.form_list.items():  # pylint: disable=no-member
            for name, field in form_item.base_fields.items():
                questions[name] = field.label
        keys = []
        for key in self.all_params:
            for step, form in self.form_list.items():
                if step in keys:
                    continue
                if "summary" in keys:
                    continue
            summary_list.append(
                {
                    key: {
                        "question": questions[key],
                        "answer": getattr(requesting_catalogue_page, key, None),
                    },
                },
            )
            keys.append(step)
        return summary_list

    def get_base_context(self, context, requesting_catalogue_page, stage, step):
        if step in ["name", "security-classification", "intended-access"]:
            context["backlink"] = reverse(
                "requesting-data-tracker", args={requesting_catalogue_page.id}
            )
        else:
            context["backlink"] = reverse(f"requesting-data-{stage}-step", args={self.steps.prev})

        if step in self.radio_input_pages:
            context["step"] = step
            current_form = self.get_form(step=step)
            radio_field = list(current_form.fields.keys())[0]
            input_field = list(current_form.fields.keys())[1]
            context["radio_field"] = radio_field
            context["radio_label"] = current_form.fields[radio_field].label
            context["radio_help_text"] = current_form.fields[radio_field].help_text
            context["input_field"] = input_field
            context["input_label"] = current_form.fields[input_field].label

        if step == "intended-access":
            context["step"] = step
            current_form = self.get_form(step=step)
            everyone_field = list(current_form.fields.keys())[0]
            department_input_field = list(current_form.fields.keys())[1]
            critera_input_field = list(current_form.fields.keys())[2]

            context["everyone_field"] = everyone_field
            context["everyone_field_label"] = current_form.fields[everyone_field].label

            context["department_input_field"] = department_input_field
            context["department_input_help_text"] = current_form.fields[
                department_input_field
            ].help_text

            context["critera_input_field"] = critera_input_field
            context["critera_input_help_text"] = current_form.fields[critera_input_field].help_text

        if step in self.user_search_pages:
            current_form = self.get_form(step=step)
            field = list(current_form.fields.keys())[0]
            context["label"] = current_form.fields[field].label
            context["help_text"] = current_form.fields[field].help_text
            self.get_user_search_context(context, step)

        return context

    def process_step(self, form):
        if "submit" in self.request.POST:
            self.storage.extra_data["action"] = "submit"
        elif "start_over" in self.request.POST:
            self.storage.extra_data["action"] = "start_over"
        print("super().process_step(form):::", super().process_step(form))
        return super().process_step(form)


class RequestingCataloguePageTitleAndDescriptionWizardView(RequestingCataloguePageBaseWizardView):
    form_list = [
        ("name", DatasetNameForm),
        ("descriptions", DatasetDescriptionsForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "name",
        "short_description",
        "description",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        context["stage"] = "Title and Description"
        step = self.steps.current
        if (
            requesting_catalogue_page.stage_one_complete
            and "/requesting-data/tracker/" in self.request.META["HTTP_REFERER"]
        ):
            context["summary"] = self.get_completed_summary_context(requesting_catalogue_page)
        else:
            context["summary"] = self.get_summary_context()

        self.get_base_context(context, requesting_catalogue_page, "title-and-description", step)

        if step == "descriptions":
            context["link_text"] = "Find out the best practice for writing descriptions."
            context["link"] = (
                "https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/creating-and-updating-a-catalogue-pages/data-descriptions/"  # pylint: disable=line-too-long
            )
        elif step in self.user_search_pages:
            context["link_text"] = (
                "Find out more information about data owner roles and responsibilities"
            )
            context["link"] = (
                "https://data-services-help.trade.gov.uk/data-workspace/how-to/data-owner-basics/managing-data-key-tasks-and-responsibilities/"  # pylint: disable=line-too-long
            )

        return context

    def done(self, form_list, **kwargs):
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        
        action = self.storage.extra_data.get("action")
        print("action:::", action)
        if action == "start_over":
            requesting_catalogue_page.stage_two_complete = False
            requesting_catalogue_page.save()
            self.storage.reset()
            print("in here")
            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )
        elif action == "submit":
            requesting_catalogue_page.user = self.request.user.id
            requesting_catalogue_page.stage_one_complete = True
            requesting_catalogue_page = self.add_fields(form_list, requesting_catalogue_page)

            requesting_catalogue_page.save()

            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )

        elif requesting_catalogue_page.stage_one_complete and action == "submit":
            requesting_catalogue_page = self.add_fields(form_list, requesting_catalogue_page)
            requesting_catalogue_page.save()
            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )

        return HttpResponseRedirect(
            reverse(
                "requesting-data-tracker",
                kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
            )
        )

    # def dispatch(self, request, *args, **kwargs):
    #     requesting_catalogue_page = get_object_or_404(RequestingDataset,  id=self.request.session["requesting_catalogue_page"])
    #     response = super().dispatch(request, *args, **kwargs)
    #     if requesting_catalogue_page.stage_one_complete:
    #         self.storage.data = requesting_catalogue_page.wizard_data["title_and_description"]
    #     return response


class RequestingCataloguePageAccessRestrictionsWizardView(RequestingCataloguePageBaseWizardView):

    form_list = [
        ("intended-access", DatasetIntendedAccessForm),
        ("user-restrictions", DatasetUserRestrictionsForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        # "intended_access",
        "user_restrictions",
    ]

    notes_fields = [
        "intended_access",
        "user_restrictions",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        step = self.steps.current
        context["stage"] = "Access Restrictions"

        if (
            requesting_catalogue_page.stage_two_complete
            and "/requesting-data/tracker/" in self.request.META["HTTP_REFERER"]
        ):
            context["summary"] = self.get_completed_summary_context(requesting_catalogue_page)
        else:
            context["summary"] = self.get_summary_context()

        self.get_base_context(context, requesting_catalogue_page, "title-and-description", step)

        if self.steps.current == "intended-access":
            context["backlink"] = reverse(
                "requesting-data-tracker", args={requesting_catalogue_page.id}
            )
        else:
            context["backlink"] = reverse(
                "requesting-data-access-restrictions-step", args={self.steps.prev}
            )
        return context

    def done(self, form_list, **kwargs):
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        action = self.storage.extra_data.get("action")
        if action == "submit":
            requesting_catalogue_page.user = self.request.user.id
            requesting_catalogue_page.stage_two_complete = True
            requesting_catalogue_page = self.add_fields(
                form_list, requesting_catalogue_page, self.notes_fields
            )
            requesting_catalogue_page.save()

            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )
        elif action == "start_over":
            requesting_catalogue_page.stage_two_complete = False
            requesting_catalogue_page.save()
            self.storage.reset()
            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )

    # def dispatch(self, request, *args, **kwargs):
    #     requesting_catalogue_page = get_object_or_404(RequestingDataset,  id=self.request.session["requesting_catalogue_page"])
    #     response = super().dispatch(request, *args, **kwargs)
    #     if requesting_catalogue_page.stage_two_complete:
    #         self.storage.data = requesting_catalogue_page.wizard_data["access_restrictions"]
    #     return response


class RequestingCataloguePageGovernanceWizardView(RequestingCataloguePageBaseWizardView):

    form_list = [
        ("information-asset-owner", DatasetInformationAssetOwnerForm),
        ("information-asset-manager", DatasetInformationAssetManagerForm),
        ("enquiries-contact", DatasetEnquiriesContactForm),
        ("licence", DatasetLicenceForm),
        ("retention-period", DatasetRetentionPeriodForm),
        # ("catalogue-editors", DatasetCatalogueEditorsForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "intended_access",
        "location_restrictions",
        "user_restrictions",
        "retention_policy",
    ]

    notes_fields = [
        "intended_access",
        "user_restrictions",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        step = self.steps.current
        context["stage"] = "Governance"
        if (
            requesting_catalogue_page.stage_three_complete
            and "/requesting-data/tracker/" in self.request.META["HTTP_REFERER"]
        ):
            context["summary"] = self.get_completed_summary_context(requesting_catalogue_page)
        else:
            context["summary"] = self.get_summary_context()

        self.get_base_context(context, requesting_catalogue_page, "title-and-description", step)

        if self.steps.current == "intended-access":
            context["backlink"] = reverse(
                "requesting-data-tracker", args={requesting_catalogue_page.id}
            )
        else:
            context["backlink"] = reverse(
                "requesting-data-access-restrictions-step", args={self.steps.prev}
            )
        return context

    def done(self, form_list, **kwargs):
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        action = self.storage.extra_data.get("action")
        requesting_catalogue_page.wizard_data["governance"] = self.storage.data
        requesting_catalogue_page.save()
        if action == "submit":
            requesting_catalogue_page.user = self.request.user.id
            requesting_catalogue_page.stage_three_complete = True
            requesting_catalogue_page = self.add_fields(
                form_list, requesting_catalogue_page, self.notes_fields
            )
            requesting_catalogue_page.save()

            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )
        elif action == "start_over":
            requesting_catalogue_page.stage_three_complete = False
            self.storage.reset()
            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )

    # def dispatch(self, request, *args, **kwargs):
    #     requesting_catalogue_page = get_object_or_404(RequestingDataset,  id=self.request.session["requesting_catalogue_page"])
    #     response = super().dispatch(request, *args, **kwargs)
    #     if requesting_catalogue_page.stage_three_complete:
    #         self.storage.data = requesting_catalogue_page.wizard_data["governance"]
    #     return response


class RequestingCataloguePageAboutThisDataWizardView(RequestingCataloguePageBaseWizardView):

    form_list = [
        # ("type", DatasetTypeForm),
        ("security-classification", DatasetSecurityClassificationForm),
        ("personal-data", DatasetPersonalDataForm),
        ("special-personal-data", DatasetSpecialPersonalDataForm),
        ("supdate-frequency", DatasetUpdateFrequencyForm),
        ("summary", SummaryPageForm),
    ]

    all_params = [
        "government_security_classification",
        "personal_data",
        "special_personal_data",
    ]

    notes_fields = [
        "special-personal-data",
    ]

    def get_template_names(self):
        return self.get_template(self.steps.current)

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        context["stage"] = "About This Data"
        step = self.steps.current
        if (
            requesting_catalogue_page.stage_four_complete
            and "/requesting-data/tracker/" in self.request.META["HTTP_REFERER"]
        ):
            context["summary"] = self.get_completed_summary_context(requesting_catalogue_page)
        else:
            context["summary"] = self.get_summary_context()

        self.get_base_context(context, requesting_catalogue_page, "title-and-description", step)
        if step == "special-personal-data":
            context["link_text"] = "Find out more information about special category personal data"
            context["link"] = "#"

        return context

    def done(self, form_list, **kwargs):
        requesting_catalogue_page = RequestingDataset.objects.get(
            id=self.request.session["requesting_catalogue_page"]
        )
        action = self.storage.extra_data.get("action")
        requesting_catalogue_page.wizard_data["about_this_data"] = self.storage.data
        requesting_catalogue_page.save()
        if action == "submit":
            requesting_catalogue_page.user = self.request.user.id
            requesting_catalogue_page.stage_four_complete = True
            requesting_catalogue_page = self.add_fields(
                form_list, requesting_catalogue_page, self.notes_fields
            )
            requesting_catalogue_page.save()

            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )
        elif action == "start_over":
            requesting_catalogue_page.stage_four_complete = False
            self.storage.reset()
            return HttpResponseRedirect(
                reverse(
                    "requesting-data-tracker",
                    kwargs={"requesting_catalogue_page_id": requesting_catalogue_page.id},
                )
            )

    # def dispatch(self, request, *args, **kwargs):
    #     requesting_catalogue_page = get_object_or_404(RequestingDataset,  id=self.request.session["requesting_catalogue_page"])
    #     response = super().dispatch(request, *args, **kwargs)
    #     if requesting_catalogue_page.stage_four_complete:
    #         self.storage.data = requesting_catalogue_page.wizard_data["about_this_data"]
    #     return response


class RequestingCataloguePageSubmission(TemplateView):
    template_name = "datasets/requesting_data/submission.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ticket_id"] = self.kwargs.get("ticket_id")
        return context
