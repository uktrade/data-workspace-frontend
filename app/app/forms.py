from django import forms

from govuk_forms.forms import GOVUKForm
from govuk_forms import widgets, fields

from app.appstream import (
    get_fleet_scale,
)

class AppstreamAdminForm(GOVUKForm):
    min_capacity, max_capacity = get_fleet_scale()

    new_min_capacity = forms.CharField(
                            label='Min value',
                            max_length=2,
                            widget=widgets.TextInput(),
                            initial=min_capacity
                            )
    new_max_capacity = forms.CharField(
                            label='Max value',
                            max_length=2,
                            widget=widgets.TextInput(),
                            initial=max_capacity
                            )
