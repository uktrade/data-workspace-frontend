from collections import defaultdict
from functools import partial
import logging
import json

from django import forms
from django.contrib.auth import get_user_model

from dataworkspace.apps.datasets.constants import AggregationType, DataSetType, TagType
from .models import DataSet, SourceLink, Tag, VisualisationCatalogueItem
from .search import SORT_FIELD_MAP, SearchDatasetsFilters
from ...forms import (
    GOVUKDesignSystemChoiceField,
    GOVUKDesignSystemForm,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
    GOVUKDesignSystemSelectWidget,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
    GOVUKDesignSystemRichTextField,
)

logger = logging.getLogger("app")


class SearchableChoice:
    def __init__(self, label, count=0):
        self.label = label
        self.count = count
        self.search_text = str(label).lower()

    def __str__(self):
        return self.label


class FilterWidget(forms.widgets.CheckboxSelectMultiple):
    template_name = "datasets/filter.html"
    option_template_name = "datasets/filter_option.html"

    def __init__(
        self,
        group_label,
        hint_text=None,
        limit_initial_options=0,
        show_more_label="Show more",
        *args,
        **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        super().__init__(*args, **kwargs)
        self._group_label = group_label
        self._hint_text = hint_text
        self._limit_initial_options = limit_initial_options
        self._show_more_label = show_more_label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["group_label"] = self._group_label
        context["widget"]["hint_text"] = self._hint_text
        context["widget"]["limit_initial_options"] = self._limit_initial_options
        context["widget"]["show_more_label"] = self._show_more_label
        return context

    class Media:
        js = ("app-filter-show-more-v2.js",)


class AccordionFilterWidget(FilterWidget):
    template_name = "datasets/accordion_filter.html"
    option_template_name = "datasets/accordion_filter_option.html"


class SortSelectWidget(forms.widgets.Select):
    template_name = "datasets/select.html"
    option_template_name = "datasets/select_option.html"

    def __init__(
        self,
        label,
        form_group_extra_css=None,
        *args,
        **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        super().__init__(*args, **kwargs)
        self._label = label
        self._form_group_extra_css = form_group_extra_css

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["label"] = self._label
        context["widget"]["form_group_extra_css"] = self._form_group_extra_css
        return context


class RequestAccessForm(GOVUKDesignSystemForm):
    email = GOVUKDesignSystemCharField(
        label="Contact email",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
    )
    goal = GOVUKDesignSystemTextareaField(
        label="Why do you need this data?",
        help_text=(
            "For example, I need to create a report for my senior management team "
            "to show performance trends and delivery against targets."
        ),
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes="govuk-!-font-weight-bold",
            attrs={"rows": 5},
        ),
        error_messages={"required": "You must provide details of why you need access."},
    )

    def __init__(self, *args, visualisation=False, **kwargs):
        super().__init__(*args, **kwargs)

        initial_email = self.initial.get("email")
        if initial_email:
            self.fields["email"].help_text = f"You are logged in as {initial_email}"
            self.fields["email"].widget.custom_context[
                "help_text"
            ] = f"You are logged in as {initial_email}"

        if visualisation:
            self.fields["goal"].label = "Why do you need this data visualisation?"
            self.fields["goal"].widget.custom_context[
                "label"
            ] = "Why do you need this data visualisation?"


class EligibilityCriteriaForm(forms.Form):
    meet_criteria = forms.TypedChoiceField(
        widget=forms.RadioSelect,
        coerce=lambda x: x == "yes",
        choices=(("no", "No"), ("yes", "Yes")),
    )
    access_request = forms.IntegerField(widget=forms.HiddenInput, required=False)


class SourceTagField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class DatasetSearchForm(forms.Form):
    SUBSCRIBED = "subscribed"
    BOOKMARKED = "bookmarked"
    OWNED = "owned"

    q = forms.CharField(required=False)

    user_access = forms.TypedMultipleChoiceField(
        choices=[
            ("yes", "Data I have access to"),
            ("no", "Data I don't have access to"),
        ],
        required=False,
        widget=AccordionFilterWidget("Data access"),
    )

    admin_filters = forms.TypedMultipleChoiceField(
        choices=[
            ("unpublished", "Include unpublished"),
            ("opendata", "Show Open data"),
            ("withvisuals", "Show datasets with Visuals"),
        ],
        coerce=str,
        required=False,
        widget=AccordionFilterWidget("Admin only options"),
    )

    my_datasets = forms.TypedMultipleChoiceField(
        choices=[
            (BOOKMARKED, "My bookmarks"),
            (SUBSCRIBED, "My subscriptions"),
            (OWNED, "Data I own or manage"),
        ],
        required=False,
        widget=AccordionFilterWidget("My datasets"),
    )

    use = forms.TypedMultipleChoiceField(
        choices=[
            (DataSetType.DATACUT, "Download data"),
            (DataSetType.MASTER, "Analyse data"),
            (DataSetType.VISUALISATION, "View dashboard"),
        ],
        coerce=int,
        required=False,
        widget=FilterWidget("What do you want to do?", hint_text="Select all that apply"),
    )

    data_type = forms.TypedMultipleChoiceField(
        choices=[
            (DataSetType.MASTER, "Source dataset"),
            (DataSetType.DATACUT, "Data cut"),
            (DataSetType.REFERENCE, "Reference dataset"),
            (DataSetType.VISUALISATION, "Visualisation"),
        ],
        coerce=int,
        required=False,
        widget=AccordionFilterWidget("Type"),
    )

    source = SourceTagField(
        queryset=Tag.objects.order_by("name").filter(type=TagType.SOURCE),
        required=False,
        widget=AccordionFilterWidget("Data source", hint_text="Select all that apply"),
    )

    topic = SourceTagField(
        queryset=Tag.objects.order_by("name").filter(type=TagType.TOPIC),
        required=False,
        widget=AccordionFilterWidget(
            "Topic",
        ),
    )

    def _get_sort_choices(self):
        return [(k, v["display_name"]) for k, v in SORT_FIELD_MAP.items()]

    def clean_sort(self):
        data = self.cleaned_data["sort"]
        if not data:
            data = self._get_sort_choices()[0][0]
        return data

    class Media:
        js = ("app-filter-show-more-v2.js",)

    def __init__(self, request, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        # Use a custom mechanism of constructing the sort field to only show the
        # search by popularity item if a flag is enabled for the current user. When
        # this gets rolled out to all users, this can be made standard
        self.request = request
        self.fields["sort"] = forms.ChoiceField(
            required=False,
            choices=self._get_sort_choices(),
            widget=SortSelectWidget(
                label="Sort by", form_group_extra_css="govuk-!-margin-bottom-0"
            ),
        )

    def annotate_and_update_filters(self, datasets, matcher):
        """
        Calculate counts of datasets that will match if users apply additional filters and apply these to the form
        labels.
        @param datasets: iterable of datasets
        @param matcher: fn which returns true when the row is matched
        @return: None
        """

        counts = {
            "my_datasets": defaultdict(int),
            "admin_filters": defaultdict(int),
            "use": defaultdict(int),
            "data_type": defaultdict(int),
            "source": defaultdict(int),
            "topic": defaultdict(int),
            "user_access": defaultdict(int),
        }

        user_access = set(self.cleaned_data["user_access"])
        selected_admin = set(self.cleaned_data["admin_filters"])
        selected_unpublished = "unpublished" in selected_admin
        selected_opendata = "opendata" in selected_admin
        selected_withvisuals = "withvisuals" in selected_admin

        selected_uses = set(self.cleaned_data["use"])
        selected_data_type = set(self.cleaned_data["data_type"])
        selected_source_ids = set(source.id for source in self.cleaned_data["source"])
        selected_topic_ids = set(topic.id for topic in self.cleaned_data["topic"])

        # Cache these locally for performance. The source model choice field can end up hitting the DB each time.
        user_access_choices = list(self.fields["user_access"].choices)
        admin_choices = list(self.fields["admin_filters"].choices)
        use_choices = list(self.fields["use"].choices)
        data_type_choices = list(self.fields["data_type"].choices)
        source_choices = list(self.fields["source"].choices)
        topic_choices = list(self.fields["topic"].choices)

        for dataset in datasets:
            dataset_matcher = partial(
                matcher,
                data=dataset,
                unpublished=selected_unpublished,
                opendata=selected_opendata,
                withvisuals=selected_withvisuals,
                use=selected_uses,
                data_type=selected_data_type,
                source_ids=selected_source_ids,
                topic_ids=selected_topic_ids,
                user_accessible=user_access == {"yes"},
                user_inaccessible=user_access == {"no"},
                selected_user_datasets=self.cleaned_data["my_datasets"],
            )

            if dataset_matcher(user_accessible=True, user_inaccessible=False):
                counts["user_access"]["yes"] += 1

            if dataset_matcher(user_inaccessible=True, user_accessible=False):
                counts["user_access"]["no"] += 1

            for value, _ in self.fields["my_datasets"].choices:
                if dataset_matcher(selected_user_datasets={value}):
                    counts["my_datasets"][value] += 1

            for admin_id, _ in admin_choices:
                if dataset_matcher(**{admin_id: True}):
                    counts["admin_filters"][admin_id] += 1

            for use_id, _ in use_choices:
                if dataset_matcher(use={use_id}):
                    counts["use"][use_id] += 1

            for type_id, _ in data_type_choices:
                if dataset_matcher(data_type={type_id}):
                    counts["data_type"][type_id] += 1

            for source_id, _ in source_choices:
                if dataset_matcher(source_ids={source_id.value}):
                    counts["source"][source_id.value] += 1

            for topic_id, _ in topic_choices:
                if dataset_matcher(topic_ids={topic_id.value}):
                    counts["topic"][topic_id.value] += 1

        self.fields["user_access"].choices = [
            (access_id, SearchableChoice(access_text, counts["user_access"][access_id]))
            for access_id, access_text in user_access_choices
        ]

        self.fields["my_datasets"].choices = [
            (
                bookmarked_id,
                SearchableChoice(value, counts["my_datasets"][bookmarked_id]),
            )
            for bookmarked_id, value in list(self.fields["my_datasets"].choices)
        ]

        self.fields["admin_filters"].choices = [
            (admin_id, SearchableChoice(admin_text, counts["admin_filters"][admin_id]))
            for admin_id, admin_text in admin_choices
        ]

        self.fields["use"].choices = [
            (use_id, use_text + f" ({counts['use'][use_id]})") for use_id, use_text in use_choices
        ]

        self.fields["data_type"].choices = [
            (type_id, SearchableChoice(type_text, counts["data_type"][type_id]))
            for type_id, type_text in data_type_choices
        ]

        self.fields["source"].choices = [
            (
                source_id,
                SearchableChoice(source_text, counts["source"][source_id.value]),
            )
            for source_id, source_text in source_choices
            if source_id.value in selected_source_ids or counts["source"][source_id.value] != 0
        ]

        self.fields["topic"].choices = [
            (
                topic_id,
                SearchableChoice(topic_text, counts["topic"][topic_id.value]),
            )
            for topic_id, topic_text in topic_choices
            if topic_id.value in selected_topic_ids or counts["topic"][topic_id.value] != 0
        ]

    def get_filters(self):
        filters = SearchDatasetsFilters()

        filters.query = self.cleaned_data.get("q")

        filters.unpublished = "unpublished" in self.cleaned_data.get("admin_filters")
        filters.open_data = "opendata" in self.cleaned_data.get("admin_filters")
        filters.with_visuals = "withvisuals" in self.cleaned_data.get("admin_filters")
        filters.use = set(self.cleaned_data.get("use"))
        filters.data_type = set(self.cleaned_data.get("data_type", []))
        filters.sort_type = SORT_FIELD_MAP.get(self.cleaned_data["sort"])
        filters.source_ids = set(source.id for source in self.cleaned_data.get("source"))
        filters.topic_ids = set(topic.id for topic in self.cleaned_data.get("topic"))
        filters.user_accessible = set(self.cleaned_data.get("user_access", [])) == {"yes"}
        filters.user_inaccessible = set(self.cleaned_data.get("user_access", [])) == {"no"}

        filters.my_datasets = set(self.cleaned_data.get("my_datasets", []))

        return filters


class RelatedMastersSortForm(forms.Form):
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("dataset__name", "A to Z"),
            ("-dataset__name", "Z to A"),
            ("-dataset__published_at", "Recently published"),
        ],
        initial="dataset__name",
        widget=SortSelectWidget(label="Sort by"),
    )


class RelatedDataCutsSortForm(forms.Form):
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("query__dataset__name", "A to Z"),
            ("-query__dataset__name", "Z to A"),
            ("-query__dataset__published_at", "Recently published"),
        ],
        initial="query__dataset__name",
        widget=SortSelectWidget(label="Sort by"),
    )


class RelatedVisualisationsSortForm(forms.Form):
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("name", "A to Z"),
            ("name", "Z to A"),
            ("published_at", "Recently published"),
        ],
        initial="name",
        widget=SortSelectWidget(label="Sort by"),
    )


class DatasetEditForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataSet
        fields = [
            "name",
            "short_description",
            "description",
            "enquiries_contact",
            "licence",
            "licence_url",
            "retention_policy",
            "personal_data",
            "restrictions_on_usage",
        ]

    name = GOVUKDesignSystemCharField(
        label="Dataset Name *",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide a name for this dataset."},
    )
    short_description = GOVUKDesignSystemCharField(
        label="Short description *",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide a short description for this dataset."},
    )
    description = GOVUKDesignSystemRichTextField(
        error_messages={"required": "You must provide a description for this dataset."},
    )
    enquiries_contact = GOVUKDesignSystemCharField(
        label="Enquiries contact",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    licence = GOVUKDesignSystemCharField(
        label="Licence",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    licence_url = GOVUKDesignSystemCharField(
        label="Licence url",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    retention_policy = GOVUKDesignSystemTextareaField(
        label="Retention policy",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    personal_data = GOVUKDesignSystemCharField(
        label="Personal data",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    restrictions_on_usage = GOVUKDesignSystemTextareaField(
        label="Restrictions on usage",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )

    def clean_enquiries_contact(self):
        if self.cleaned_data["enquiries_contact"]:
            try:
                user = get_user_model().objects.get(email=self.cleaned_data["enquiries_contact"])
            except get_user_model().DoesNotExist as e:
                raise forms.ValidationError("User email address does not exist") from e
            else:
                return user
        else:
            return None

    def clean_authorized_email_domains(self):
        return json.dumps(self.cleaned_data["authorized_email_domains"].split(","))


class VisualisationCatalogueItemEditForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = VisualisationCatalogueItem
        fields = [
            "name",
            "short_description",
            "description",
            "enquiries_contact",
            "secondary_enquiries_contact",
            "licence",
            "licence_url",
            "retention_policy",
            "personal_data",
            "restrictions_on_usage",
        ]

    name = GOVUKDesignSystemCharField(
        label="Dataset Name *",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide a name for this dataset."},
    )
    short_description = GOVUKDesignSystemCharField(
        label="Short description *",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide a short description for this dataset."},
    )

    description = GOVUKDesignSystemRichTextField(
        error_messages={"required": "You must provide a description for this dataset."},
    )

    enquiries_contact = GOVUKDesignSystemCharField(
        label="Enquiries contact",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    secondary_enquiries_contact = GOVUKDesignSystemCharField(
        label="Secondary enquiries contact",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    licence = GOVUKDesignSystemCharField(
        label="Licence",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    licence_url = GOVUKDesignSystemCharField(
        label="Licence url",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    retention_policy = GOVUKDesignSystemTextareaField(
        label="Retention policy",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    personal_data = GOVUKDesignSystemCharField(
        label="Personal data",
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )
    restrictions_on_usage = GOVUKDesignSystemTextareaField(
        label="Restrictions on usage",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        required=False,
    )

    def clean_enquiries_contact(self):
        if self.cleaned_data["enquiries_contact"]:
            try:
                user = get_user_model().objects.get(email=self.cleaned_data["enquiries_contact"])
            except get_user_model().DoesNotExist as e:
                raise forms.ValidationError("User email address does not exist") from e
            else:
                return user
        else:
            return None

    def clean_secondary_enquiries_contact(self):
        if self.cleaned_data["secondary_enquiries_contact"]:
            try:
                user = get_user_model().objects.get(
                    email=self.cleaned_data["secondary_enquiries_contact"]
                )
            except get_user_model().DoesNotExist as e:
                raise forms.ValidationError("User email address does not exist") from e
            else:
                return user
        else:
            return None

    def clean_authorized_email_domains(self):
        return json.dumps(self.cleaned_data["authorized_email_domains"].split(","))


class UserSearchForm(GOVUKDesignSystemForm):
    search = GOVUKDesignSystemTextareaField(
        label="Enter one or more email addresses on separate lines or search for a single user by name.",
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False, extra_label_classes="govuk-!-font-weight-bold"
        ),
        error_messages={"required": "You must provide a search term."},
    )


class ChartSourceSelectForm(forms.Form):
    source = GOVUKDesignSystemRadioField(
        required=True,
        label="Select the source data you want to create a chart from",
        widget=GOVUKDesignSystemRadiosWidget(heading="p", extra_label_classes="govuk-body-l"),
    )

    def __init__(self, *args, **kwargs):
        dataset = kwargs.pop("dataset")
        super().__init__(*args, **kwargs)
        self.fields["source"].choices = (
            (x.id, x.name) for x in dataset.related_objects() if not isinstance(x, SourceLink)
        )


class ChartAggregateForm(GOVUKDesignSystemForm):
    filters = forms.JSONField(widget=forms.HiddenInput(), required=False)
    sort_direction = forms.CharField(widget=forms.HiddenInput())
    sort_field = forms.CharField(widget=forms.HiddenInput())
    columns = forms.JSONField(widget=forms.HiddenInput())
    aggregate = GOVUKDesignSystemChoiceField(
        choices=AggregationType.choices,
        label="Aggregate type",
        widget=GOVUKDesignSystemSelectWidget(label_is_heading=False),
    )
    aggregate_field = GOVUKDesignSystemChoiceField(
        required=False,
        label="Aggregate field",
        widget=GOVUKDesignSystemSelectWidget(
            label_is_heading=False, attrs={"disabled": "disabled"}
        ),
    )
    group_by = GOVUKDesignSystemChoiceField(
        required=False,
        label="Group by",
        widget=GOVUKDesignSystemSelectWidget(
            label_is_heading=False, attrs={"disabled": "disabled"}
        ),
    )

    def __init__(self, *args, **kwargs):
        self.column_config = {x["field"]: x["dataType"] for x in kwargs.pop("columns")}
        super().__init__(*args, **kwargs)
        self.fields["group_by"].choices = ((x, x) for x in self.column_config.keys())
        self.fields["aggregate_field"].choices = (
            (k, f"{k} ({v})") for k, v in self.column_config.items()
        )

    def clean(self):
        # Only allow sum/avg/min/max on numeric fields
        cleaned_data = super().clean()
        aggregate_type = cleaned_data["aggregate"]
        aggregate_data_type = self.column_config.get(cleaned_data["aggregate_field"])
        if (
            aggregate_type
            not in [
                AggregationType.NONE.value,
                AggregationType.COUNT.value,
            ]
            and aggregate_data_type != "numeric"
        ):
            err = f"Unable to {aggregate_type} {aggregate_data_type} fields. Select a numeric field to continue"
            self.fields["aggregate_field"].widget.custom_context["errors"] = [err]
            raise forms.ValidationError({"aggregate_field": err})
        return cleaned_data
