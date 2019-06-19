from django import forms

from app.appstream import (
    get_fleet_scale,
)


class AppstreamAdminForm(forms.Form):
    min_capacity, max_capacity = get_fleet_scale()

    new_min_capacity = forms.CharField(
        label='Minimum desired instances',
        max_length=2,
        widget=forms.TextInput(attrs={'class': 'govuk-input govuk-input--width-3'}),
        initial=min_capacity
    )
    new_max_capacity = forms.CharField(
        label='Maximum desired instances',
        max_length=2,
        widget=forms.TextInput(attrs={'class': 'govuk-input govuk-input--width-3'}),
        initial=max_capacity
    )
