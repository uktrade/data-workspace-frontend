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
        **kwargs  # pylint: disable=keyword-arg-before-vararg
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
        js = ('app-filter-show-more.js',)


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

    use = forms.MultipleChoiceField(
        choices=[
            (DataSetType.DATACUT.value, 'Download'),
            (DataSetType.MASTER.value, 'Analyse in tools'),
            (DataSetType.REFERENCE.value, 'Use as reference data'),
            (DataSetType.VISUALISATION.value, 'View data visualisation'),
        ],
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
        js = ('app-filter-show-more.js',)
