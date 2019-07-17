from django import forms


class ReferenceDataFieldInlineForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'style': 'text-transform:lowercase'
            }
        )
    )
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': '1'
            }
        )
    )

    def clean_name(self):
        return self.cleaned_data['name'].lower()


class ReferenceDataRecordEditForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop('reference_dataset')
        self.record_id = kwargs.pop('record_id')
        super().__init__(*args, **kwargs)
        # Build the form fields using associated ReferenceDataField objects
        for field in self.reference_dataset.fields.all():
            self.fields[field.name.lower()] = field.get_form_field()

    def clean(self):
        # Ensure duplicate identifiers are not added within a reference dataset
        id_field = self.reference_dataset.identifier_field.name.lower()
        if id_field in self.cleaned_data:
            id_value = self.cleaned_data[id_field]
            existing = self.reference_dataset.get_record_by_custom_id(id_value)
            if self.record_id is None:
                if existing is not None:
                    raise forms.ValidationError({
                        id_field: 'A record with this identifier already exists'
                    })
            else:
                if existing is not None and existing['dw_int_id'] != self.record_id:
                    raise forms.ValidationError({
                        id_field: 'A record with this identifier already exists'
                    })


class ReferenceDataRowDeleteForm(forms.Form):
    id = forms.CharField(
        widget=forms.HiddenInput()
    )
