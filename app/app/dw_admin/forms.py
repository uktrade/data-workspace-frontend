from django import forms


class ReferenceDataFieldInlineForm(forms.ModelForm):
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': '1'
            }
        )
    )

    def clean_data_type(self):
        # Do not allow users to change the data type of a column
        # if that column has existing data.
        orig_data_type = self.instance.data_type
        new_data_type = self.cleaned_data['data_type']
        if self.instance.id is not None and new_data_type != orig_data_type:
            matching_records = self.instance.reference_dataset.get_records().exclude(**{
                self.instance.column_name: None
            })
            if matching_records.exists():
                raise forms.ValidationError(
                    'Unable to change data type when data exists in column'
                )
        return new_data_type


class ReferenceDataRowDeleteForm(forms.Form):
    id = forms.CharField(
        widget=forms.HiddenInput()
    )


def clean_identifier(form):
    """
    Helper function for validating dynamically created reference dataset identifier field.
    Checks that supplied identifier value is unique for this reference data set
    :param form:
    :return:
    """
    field = form.instance
    reference_dataset = form.cleaned_data['reference_dataset']
    id_field = reference_dataset.identifier_field.column_name
    cleaned_data = form.cleaned_data
    if id_field in cleaned_data:
        exists = reference_dataset.get_records().filter(**{
            id_field: cleaned_data[id_field]
        }).exclude(
            id=field.id
        )
        if exists:
            raise forms.ValidationError(
                'A record with this identifier already exists'
            )
    return cleaned_data[id_field]
