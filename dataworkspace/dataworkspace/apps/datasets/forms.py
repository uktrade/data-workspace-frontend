from collections import defaultdict
from functools import partial

from django import forms

from dataworkspace.apps.datasets.constants import DataSetType
from .models import SourceTag


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


class RequestAccessForm(forms.Form):
    email = forms.CharField(widget=forms.TextInput, required=True)
    goal = forms.CharField(widget=forms.Textarea, required=True)


class EligibilityCriteriaForm(forms.Form):
    meet_criteria = forms.TypedChoiceField(
        widget=forms.RadioSelect,
        coerce=lambda x: x == 'yes',
        choices=(('no', 'No'), ('yes', 'Yes')),
    )


class DatasetSearchForm(forms.Form):
    q = forms.CharField(required=False)

    access = forms.MultipleChoiceField(
        choices=[('yes', 'You have access')],
        required=False,
        widget=FilterWidget("Access status"),
    )

    use = forms.TypedMultipleChoiceField(
        choices=[
            (DataSetType.DATACUT.value, 'Download'),
            (DataSetType.MASTER.value, 'Analyse in tools'),
            (DataSetType.REFERENCE.value, 'Use as reference data'),
            (DataSetType.VISUALISATION.value, 'View data visualisation'),
        ],
        coerce=int,
        required=False,
        widget=FilterWidget("Purpose", hint_text="What do you want to do with data?"),
    )

    source = forms.ModelMultipleChoiceField(
        queryset=SourceTag.objects.order_by('name').all(),
        required=False,
        widget=FilterWidget(
            "Source",
            hint_text="Source or publishing organisation",
            limit_initial_options=10,
            show_more_label="Show more sources",
        ),
    )

    class Media:
        js = ('app-filter-show-more-v2.js',)

    def annotate_and_update_filters(self, datasets, matcher, number_of_matches):
        counts = {
            "access": defaultdict(int),
            "use": defaultdict(int),
            "source": defaultdict(int),
        }

        selected_access = bool(self.cleaned_data['access'])
        selected_uses = set(self.cleaned_data['use'])
        selected_source_ids = set(source.id for source in self.cleaned_data['source'])

        # Cache these locally for performance. The source model choice field can end up hitting the DB each time.
        use_choices = list(self.fields['use'].choices)
        source_choices = list(self.fields['source'].choices)

        for dataset in datasets:
            dataset_matcher = partial(
                matcher,
                data=dataset,
                access=selected_access,
                use=selected_uses,
                source_ids=selected_source_ids,
            )

            if dataset_matcher(access=True):
                counts['access']['yes'] += 1

            for use_id, _ in use_choices:
                if dataset_matcher(use={use_id}):
                    counts['use'][use_id] += 1

            for source_id, _ in source_choices:
                if dataset_matcher(source_ids={source_id}):
                    counts['source'][source_id] += 1

        self.fields['access'].choices = [
            (access_id, access_text + f" ({counts['access'][access_id]})")
            for access_id, access_text in self.fields['access'].choices
        ]

        self.fields['use'].choices = [
            (use_id, use_text + f" ({counts['use'][use_id]})")
            for use_id, use_text in use_choices
        ]

        self.fields['source'].choices = [
            (source_id, source_text + f" ({counts['source'][source_id]})")
            for source_id, source_text in source_choices
            if source_id in selected_source_ids or counts['source'][source_id] != 0
        ]
