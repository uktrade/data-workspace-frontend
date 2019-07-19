from django import forms


class ReferenceDataFieldInlineForm(forms.ModelForm):
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': '1'
            }
        )
    )


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
