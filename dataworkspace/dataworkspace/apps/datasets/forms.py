from django import forms
from .models import SourceTag
from dataworkspace.apps.datasets.constants import DataSetType


class FilterWidget(forms.widgets.CheckboxSelectMultiple):
    template_name = 'datasets/filter.html'
    option_template_name = "datasets/filter_option.html"

    def __init__(self, group_label, hint_text=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._group_label = group_label
        self._hint_text = hint_text

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['group_label'] = self._group_label
        context['widget']['hint_text'] = self._hint_text
        return context


class RequestAccessForm(forms.Form):
    email = forms.CharField(widget=forms.TextInput, required=True)
    goal = forms.CharField(widget=forms.Textarea, required=True)


class EligibilityCriteriaForm(forms.Form):
    meet_criteria = forms.TypedChoiceField(
        widget=forms.RadioSelect,
        coerce=lambda x: True if x == 'yes' else False,
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
            (DataSetType.REFERENCE.value, 'Reference'),
        ],
        required=False,
        widget=FilterWidget("Purpose", hint_text="Select all that apply."),
    )

    source = forms.ModelMultipleChoiceField(
        queryset=SourceTag.objects.order_by('name').all(),
        required=False,
        widget=FilterWidget("Source", hint_text="Select all that apply."),
    )
