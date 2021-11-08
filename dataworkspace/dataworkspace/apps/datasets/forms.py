from collections import defaultdict
from functools import partial

from django import forms

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from .models import Tag
from ...forms import (
    GOVUKDesignSystemForm,
    GOVUKDesignSystemCharField,
    GOVUKDesignSystemTextWidget,
    GOVUKDesignSystemTextareaField,
    GOVUKDesignSystemTextareaWidget,
)


class FilterWidget(forms.widgets.CheckboxSelectMultiple):
    template_name = 'datasets/filter.html'
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
        context['widget']['group_label'] = self._group_label
        context['widget']['hint_text'] = self._hint_text
        context['widget']['limit_initial_options'] = self._limit_initial_options
        context['widget']['show_more_label'] = self._show_more_label
        return context

    class Media:
        js = ('app-filter-show-more-v2.js',)


class ScrollingFilterWidget(FilterWidget):
    template_name = 'datasets/scrolling_filter.html'
    option_template_name = "datasets/scrolling_filter_option.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        selected_count = 0
        for _, options, __ in context['widget']['optgroups']:
            for option in options:
                if option['attrs'].get('checked', False):
                    selected_count += 1

        context['widget']['selected_count'] = selected_count

        return context


class SortSelectWidget(forms.widgets.Select):
    template_name = 'datasets/select.html'
    option_template_name = 'datasets/select_option.html'

    def __init__(
        self, label, *args, **kwargs,  # pylint: disable=keyword-arg-before-vararg
    ):
        super().__init__(*args, **kwargs)
        self._label = label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['label'] = self._label
        return context


class RequestAccessForm(GOVUKDesignSystemForm):
    email = GOVUKDesignSystemCharField(
        label="Contact email",
        required=True,
        widget=GOVUKDesignSystemTextWidget(
            label_is_heading=False, extra_label_classes='govuk-!-font-weight-bold'
        ),
    )
    goal = GOVUKDesignSystemTextareaField(
        label="Why do you need this data?",
        help_text=(
            'For example, I need to create a report for my senior management team '
            'to show performance trends and delivery against targets.'
        ),
        required=True,
        widget=GOVUKDesignSystemTextareaWidget(
            label_is_heading=False,
            extra_label_classes='govuk-!-font-weight-bold',
            attrs={"rows": 5},
        ),
        error_messages={"required": "You must provide details of why you need access."},
    )

    def __init__(self, *args, visualisation=False, **kwargs):
        super().__init__(*args, **kwargs)

        initial_email = self.initial.get("email")
        if initial_email:
            self.fields['email'].help_text = f"You are logged in as {initial_email}"
            self.fields['email'].widget.custom_context[
                'help_text'
            ] = f"You are logged in as {initial_email}"

        if visualisation:
            self.fields['goal'].label = "Why do you need this data visualisation?"
            self.fields['goal'].widget.custom_context[
                'label'
            ] = "Why do you need this data visualisation?"


class EligibilityCriteriaForm(forms.Form):
    meet_criteria = forms.TypedChoiceField(
        widget=forms.RadioSelect,
        coerce=lambda x: x == 'yes',
        choices=(('no', 'No'), ('yes', 'Yes')),
    )
    access_request = forms.IntegerField(widget=forms.HiddenInput, required=False)


class SourceTagField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class DatasetSearchForm(forms.Form):
    q = forms.CharField(required=False)

    user_access = forms.TypedMultipleChoiceField(
        choices=[
            ('yes', 'Data I have access to'),
            ('no', 'Data I don\'t have access to'),
        ],
        required=False,
        widget=FilterWidget("Choose data access", hint_text="Select all that apply"),
    )

    admin_filters = forms.TypedMultipleChoiceField(
        choices=[
            ('unpublished', 'Include unpublished'),
            ('opendata', 'Show Open data'),
            ('withvisuals', 'Show datasets with Visuals'),
        ],
        coerce=str,
        required=False,
        widget=FilterWidget("Admin only options"),
    )

    bookmarked = forms.MultipleChoiceField(
        choices=[('yes', 'My bookmarks')],
        required=False,
        widget=FilterWidget("Bookmarks"),
    )

    use = forms.TypedMultipleChoiceField(
        choices=[
            (DataSetType.DATACUT, 'Download data'),
            (DataSetType.MASTER, 'Analyse data'),
            (DataSetType.VISUALISATION, 'View dashboard'),
        ],
        coerce=int,
        required=False,
        widget=FilterWidget(
            "What do you want to do?", hint_text="Select all that apply"
        ),
    )

    data_type = forms.TypedMultipleChoiceField(
        choices=[
            (DataSetType.MASTER, 'Master dataset'),
            (DataSetType.DATACUT, 'Data cut'),
            (DataSetType.REFERENCE, 'Reference dataset'),
        ],
        coerce=int,
        required=False,
        widget=FilterWidget("Choose data type", hint_text="Select all that apply"),
    )

    source = SourceTagField(
        queryset=Tag.objects.order_by('name').filter(type=TagType.SOURCE),
        required=False,
        widget=ScrollingFilterWidget("Choose data source",),
    )

    topic = SourceTagField(
        queryset=Tag.objects.order_by('name').filter(type=TagType.TOPIC),
        required=False,
        widget=FilterWidget(
            "Choose data topic",
            limit_initial_options=10,
            show_more_label="Show more topics",
            hint_text="Select all that apply",
        ),
    )

    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('-search_rank,name', 'Relevance'),
            ('-published_at', 'Date published: newest'),
            ('published_at', 'Date published: oldest'),
            ('name', 'Alphabetical (A-Z)'),
        ],
        widget=SortSelectWidget(label='Sort by'),
    )

    def clean_sort(self):
        data = self.cleaned_data['sort']
        if not data:
            data = '-search_rank,name'

        return data

    class Media:
        js = ('app-filter-show-more-v2.js',)

    def annotate_and_update_filters(self, datasets, matcher, number_of_matches):
        counts = {
            "bookmarked": defaultdict(int),
            "admin_filters": defaultdict(int),
            "use": defaultdict(int),
            "data_type": defaultdict(int),
            "source": defaultdict(int),
            "topic": defaultdict(int),
            "user_access": defaultdict(int),
        }

        user_access = set(self.cleaned_data['user_access'])
        selected_bookmark = bool(self.cleaned_data['bookmarked'])
        selected_admin = set(self.cleaned_data['admin_filters'])
        selected_unpublished = 'unpublished' in selected_admin
        selected_opendata = 'opendata' in selected_admin
        selected_withvisuals = 'withvisuals' in selected_admin

        selected_uses = set(self.cleaned_data['use'])
        selected_data_type = set(self.cleaned_data['data_type'])
        selected_source_ids = set(source.id for source in self.cleaned_data['source'])
        selected_topic_ids = set(topic.id for topic in self.cleaned_data['topic'])

        # Cache these locally for performance. The source model choice field can end up hitting the DB each time.
        user_access_choices = list(self.fields['user_access'].choices)
        admin_choices = list(self.fields['admin_filters'].choices)
        use_choices = list(self.fields['use'].choices)
        data_type_choices = list(self.fields['data_type'].choices)
        source_choices = list(self.fields['source'].choices)
        topic_choices = list(self.fields['topic'].choices)

        for dataset in datasets:
            dataset_matcher = partial(
                matcher,
                data=dataset,
                bookmark=selected_bookmark,
                unpublished=selected_unpublished,
                opendata=selected_opendata,
                withvisuals=selected_withvisuals,
                use=selected_uses,
                data_type=selected_data_type,
                source_ids=selected_source_ids,
                topic_ids=selected_topic_ids,
                user_accessible=user_access == {'yes'},
                user_inaccessible=user_access == {'no'},
            )

            if dataset_matcher(user_accessible=True, user_inaccessible=False):
                counts['user_access']['yes'] += 1

            if dataset_matcher(user_inaccessible=True, user_accessible=False):
                counts['user_access']['no'] += 1

            if dataset_matcher(bookmark=True):
                counts['bookmarked']['yes'] += 1

            for admin_id, _ in admin_choices:
                if dataset_matcher(**{admin_id: True}):
                    counts['admin_filters'][admin_id] += 1

            for use_id, _ in use_choices:
                if dataset_matcher(use={use_id}):
                    counts['use'][use_id] += 1

            for type_id, _ in data_type_choices:
                if dataset_matcher(data_type={type_id}):
                    counts['data_type'][type_id] += 1

            for source_id, _ in source_choices:
                if dataset_matcher(source_ids={source_id.value}):
                    counts['source'][source_id.value] += 1

            for topic_id, _ in topic_choices:
                if dataset_matcher(topic_ids={topic_id.value}):
                    counts['topic'][topic_id.value] += 1

        self.fields['user_access'].choices = [
            (access_id, access_text + f" ({counts['user_access'][access_id]})")
            for access_id, access_text in user_access_choices
        ]

        self.fields['bookmarked'].choices = [
            (
                bookmarked_id,
                bookmarked_text + f" ({counts['bookmarked'][bookmarked_id]})",
            )
            for bookmarked_id, bookmarked_text in self.fields['bookmarked'].choices
        ]

        self.fields['admin_filters'].choices = [
            (admin_id, admin_text + f" ({counts['admin_filters'][admin_id]})")
            for admin_id, admin_text in admin_choices
        ]

        self.fields['use'].choices = [
            (use_id, use_text + f" ({counts['use'][use_id]})")
            for use_id, use_text in use_choices
        ]

        self.fields['data_type'].choices = [
            (type_id, type_text + f" ({counts['data_type'][type_id]})")
            for type_id, type_text in data_type_choices
        ]

        self.fields['source'].choices = [
            (
                source_id,
                SearchableChoice(source_text, counts['source'][source_id.value]),
            )
            for source_id, source_text in source_choices
            if source_id.value in selected_source_ids
            or counts['source'][source_id.value] != 0
        ]

        self.fields['topic'].choices = [
            (topic_id, topic_text + f" ({counts['topic'][topic_id.value]})")
            for topic_id, topic_text in topic_choices
            if topic_id.value in selected_topic_ids
            or counts['topic'][topic_id.value] != 0
        ]


class SearchableChoice:
    def __init__(self, label, count=0):
        self.label = label
        self.count = count
        self.search_text = str(label).lower()

    def __str__(self):
        return self.label


class RelatedMastersSortForm(forms.Form):
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('dataset__name', 'A to Z'),
            ('-dataset__name', 'Z to A'),
            ('-dataset__published_at', 'Recently published'),
        ],
        initial="dataset__name",
        widget=SortSelectWidget(label='Sort by'),
    )


class RelatedDataCutsSortForm(forms.Form):
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('query__dataset__name', 'A to Z'),
            ('-query__dataset__name', 'Z to A'),
            ('-query__dataset__published_at', 'Recently published'),
        ],
        initial="query__dataset__name",
        widget=SortSelectWidget(label='Sort by'),
    )
