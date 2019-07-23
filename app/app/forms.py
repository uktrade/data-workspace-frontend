from django import forms

from app.appstream import (
    get_fleet_scale,
)


class AppstreamAdminForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        new_min_capacity, new_max_capacity = get_fleet_scale()
        self.fields['new_min_capacity'].initial = new_min_capacity
        self.fields['new_max_capacity'].initial = new_max_capacity

    new_min_capacity = forms.CharField(
        label='Minimum desired instances',
        max_length=2,
        widget=forms.TextInput(attrs={'class': 'govuk-input govuk-input--width-3', 'type': 'number'})
    )
    new_max_capacity = forms.CharField(
        label='Maximum desired instances',
        max_length=2,
        widget=forms.TextInput(attrs={'class': 'govuk-input govuk-input--width-3', 'type': 'number'}),
    )


class SupportForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label='Your email address',
        widget=forms.EmailInput(attrs={'class': 'govuk-input'}),
    )
    message = forms.CharField(
        required=True,
        label='Description',
        widget=forms.Textarea(attrs={'class': 'govuk-textarea'}),
        help_text=(
            'If you want to provide feedback or a suggestion, describe it here. '
            'If you were having a problem, explain what you did, what happened and '
            'what you expected to happen.'
        )
    )
    attachment1 = forms.FileField(
        label='Please attach screenshots or small data files.',
        help_text='Do not submit sensitive data.',
        widget=forms.FileInput(attrs={'class': 'govuk-file-upload'}),
        required=False
    )
    attachment2 = forms.FileField(
        label='',
        widget=forms.FileInput(attrs={'class': 'govuk-file-upload'}),
        required=False
    )
    attachment3 = forms.FileField(
        label='',
        widget=forms.FileInput(attrs={'class': 'govuk-file-upload'}),
        required=False
    )


class RequestAccessForm(forms.Form):
    email = forms.CharField(widget=forms.TextInput, required=True)
    justification = forms.CharField(widget=forms.Textarea, required=True)
    team = forms.CharField(widget=forms.TextInput, required=True)
