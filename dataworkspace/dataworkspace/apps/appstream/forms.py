from django import forms

from dataworkspace.apps.appstream.utils import get_fleet_scale


class AppstreamAdminForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        new_min_capacity, new_max_capacity = get_fleet_scale()
        self.fields["new_min_capacity"].initial = new_min_capacity
        self.fields["new_max_capacity"].initial = new_max_capacity

    new_min_capacity = forms.CharField(
        label="Minimum desired instances",
        max_length=2,
        widget=forms.TextInput(
            attrs={"class": "govuk-input govuk-input--width-3", "type": "number"}
        ),
    )
    new_max_capacity = forms.CharField(
        label="Maximum desired instances",
        max_length=2,
        widget=forms.TextInput(
            attrs={"class": "govuk-input govuk-input--width-3", "type": "number"}
        ),
    )
