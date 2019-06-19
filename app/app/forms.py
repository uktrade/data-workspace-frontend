from django import forms

from app.appstream import (
    get_fleet_scale,
)

class AppstreamAdminForm(forms.Form):
    min_capacity, max_capacity = get_fleet_scale()

    new_min_capacity = forms.CharField(
                            label='Min value',
                            max_length=2,
                            widget=forms.TextInput,
                            initial=min_capacity
                            )
    new_max_capacity = forms.CharField(
                            label='Max value',
                            max_length=2,
                            widget=forms.TextInput,
                            initial=max_capacity
                            )
