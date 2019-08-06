from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

from app.models import SourceLink, DataSet


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


class DataSetForm(forms.ModelForm):
    requires_authorization = forms.BooleanField(
        label='Each user must be individually authorized to access the data',
        required=False,
    )

    class Meta:
        model = DataSet
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        is_instance = 'instance' in kwargs and kwargs['instance']
        self.fields['requires_authorization'].initial = \
            kwargs['instance'].user_access_type == 'REQUIRES_AUTHORIZATION' if is_instance else \
            True


class SourceLinkForm(forms.ModelForm):
    class Meta:
        fields = ('name', 'url', 'format', 'frequency')
        model = SourceLink


class SourceLinkFormSet(BaseInlineFormSet):
    def clean(self):
        """
        Check if local files can be accessed before we try deleting
        them as part of model delete
        :return:
        """
        to_delete = [x for x in getattr(self, 'cleaned_data', []) if x.get('DELETE')]
        for form in to_delete:
            link = form['id']
            if link.link_type == link.TYPE_LOCAL:
                if not link.local_file_is_accessible():
                    raise ValidationError(
                        'Unable to access local file for deletion'
                    )


class SourceLinkUploadForm(forms.ModelForm):
    file = forms.FileField(required=True)

    class Meta:
        model = SourceLink
        fields = ('dataset', 'name', 'format', 'frequency', 'file')
        widgets = {
            'dataset': forms.HiddenInput()
        }
