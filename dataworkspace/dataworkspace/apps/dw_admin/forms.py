import csv

from django import forms
from django.core import validators
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from adminsortable2.admin import CustomInlineFormSet

from dataworkspace.apps.datasets.model_utils import has_circular_link
from dataworkspace.apps.datasets.models import SourceLink, DataSet, ReferenceDataset, \
    ReferenceDatasetField


class ReferenceDatasetForm(forms.ModelForm):
    model = ReferenceDataset

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sort_field'].queryset = self.instance.fields.all()


class ReferenceDataInlineFormset(CustomInlineFormSet):
    model = ReferenceDatasetField

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs.update({'parent': self.instance})
        return kwargs

    def _get_all_values_for_field(self, field):
        """
        Return the value for `field` in all related forms
        :param field:
        :return:
        """
        return [
            x.cleaned_data[field] for x in self.forms
            if x.cleaned_data.get(field) and not x.cleaned_data['DELETE']
        ]

    def clean(self):
        # Ensure one and only one field is set as identifier
        identifiers = self._get_all_values_for_field('is_identifier')
        if not identifiers:
            raise forms.ValidationError(
                'Please ensure one field is set as the unique identifier'
            )
        if len(identifiers) > 1:
            raise forms.ValidationError(
                'Please select only one unique identifier field'
            )

        # Ensure column names don't clash
        column_names = self._get_all_values_for_field('column_name')
        if len(column_names) != len(set(column_names)):
            raise forms.ValidationError(
                'Please ensure column names are unique'
            )

        # Ensure field names are not duplicated
        names = [
            x.cleaned_data['name'] for x in self.forms
            if x.cleaned_data.get('name') is not None
        ]
        if len(names) != len(set(names)):
            raise forms.ValidationError(
                'Please ensure field names are unique'
            )

        # Ensure one and only one field is set as the display name field
        display_names = self._get_all_values_for_field('is_display_name')
        if not display_names:
            raise forms.ValidationError(
                'Please ensure one field is set as the display name'
            )
        if len(display_names) > 1:
            raise forms.ValidationError(
                'Please select only one display name field'
            )


class ReferenceDataFieldInlineForm(forms.ModelForm):
    _reserved_column_names = ('id', 'reference_dataset', 'reference_dataset_id', 'updated_date')
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': '1'
            }
        )
    )

    class Meta:
        model = ReferenceDatasetField
        fields = (
            'name', 'column_name', 'data_type', 'linked_reference_dataset',
            'description', 'is_identifier', 'is_display_name', 'sort_order',
        )

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)
        # Hide the option of a linked reference dataset if none exist to link to
        if not self.fields['linked_reference_dataset'].queryset.exists():
            self.fields['data_type'].choices = [
                x for x in self.fields['data_type'].choices
                if x[0] != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            ]

        # Hide the linked dataset add/edit buttons on the inline formset
        self.fields['linked_reference_dataset'].widget.can_add_related = False
        self.fields['linked_reference_dataset'].widget.can_change_related = False
        self.fields['linked_reference_dataset'].widget.can_delete_related = False

        if self.instance.id:
            # Do not allow changing the data type of a foreign key
            if self.instance.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                self.fields['data_type'].disabled = True
            # Disable the relationship selector if the data type is not foreign key
            elif self.fields['linked_reference_dataset'].initial is None:
                self.fields['linked_reference_dataset'].disabled = True

    def clean_linked_reference_dataset(self):
        cleaned = self.cleaned_data
        field = self.instance
        if cleaned.get('data_type') == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
            # Ensure a reference dataset to link to was provided
            if cleaned.get('linked_reference_dataset') is None:
                raise ValidationError('Please select a reference data set to link to')

            # Ensure a reference dataset field cannot link to it's own parent
            if self.reference_dataset == cleaned['linked_reference_dataset']:
                raise ValidationError(
                    'A reference dataset record cannot point to itself'
                )

            # Do not allow users to change a foreign key relationship if records exist
            if field.id and cleaned['linked_reference_dataset'] != field.linked_reference_dataset:
                matching_records = self.reference_dataset.get_records().exclude(**{
                    field.column_name: None
                })
                if matching_records.exists():
                    raise forms.ValidationError(
                        'Unable to change linked reference dataset when '
                        'relations exist in this dataset'
                    )

            # If this reference dataset syncs with an external database we need
            # to ensure any linked fields also sync with the same database
            ext_db = self.reference_dataset.external_database
            linked_ext_db = cleaned['linked_reference_dataset'].external_database
            if ext_db is not None and ext_db != linked_ext_db:
                raise forms.ValidationError(
                    'Linked reference dataset does not exist on external database {}'.format(
                        ext_db.memorable_name
                    )
                )

            # Ensure a linked to reference dataset doesn't link back to this dataset
            if has_circular_link(self.reference_dataset, cleaned['linked_reference_dataset']):
                raise ValidationError(
                    'Unable to link to a dataset that links to this dataset'
                )

        return cleaned['linked_reference_dataset']

    def clean_data_type(self):
        orig_data_type = self.instance.data_type
        new_data_type = self.cleaned_data['data_type']

        if self.instance.id is not None:
            # Do not allow changing from foreign key to another data type
            if new_data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY and \
                    orig_data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                raise forms.ValidationError('Linked reference dataset data type cannot be updated')

            # Do not allow changing from another data type to foreign key
            if new_data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY and \
                    orig_data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                raise forms.ValidationError('Data type cannot be changed to linked reference dataset')

            # Do not allow users to change the data type of a column
            # if that column has existing data.
            if new_data_type != orig_data_type:
                matching_records = self.instance.reference_dataset.get_records().exclude(**{
                    self.instance.column_name: None
                })
                if matching_records.exists():
                    raise forms.ValidationError(
                        'Unable to change data type when data exists in column'
                    )

        return new_data_type

    def clean_is_identifier(self):
        cleaned = self.cleaned_data
        # Do not allow a foreign key field to be set as an identifier
        if cleaned.get('is_identifier') and \
                cleaned.get('data_type') == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
            raise ValidationError(
                'Identifier field cannot be linked reference data type'
            )
        return cleaned.get('is_identifier')

    def clean_column_name(self):
        column_name = self.cleaned_data['column_name']
        if column_name in self._reserved_column_names:
            raise forms.ValidationError(
                '"{}" is a reserved column name (along with: "{}")'.format(
                    column_name,
                    '", "'.join([x for x in self._reserved_column_names if x != column_name])
                )
            )
        return column_name


class ReferenceDataRowDeleteForm(forms.Form):
    id = forms.CharField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop('reference_dataset')
        super().__init__(*args, **kwargs)

    def clean(self):
        # Do not allow deletion of records that are linked to by other records
        linking_fields = ReferenceDatasetField.objects.filter(
            linked_reference_dataset=self.reference_dataset
        )

        conflicts = []
        for field in linking_fields:
            conflicts += field.reference_dataset.get_records().filter(**{
                '{}__id'.format(field.column_name): self.cleaned_data.get('id')
            })

        if conflicts:
            error_template = get_template('admin/inc/delete_linked_to_record_error.html')
            raise forms.ValidationError(
                mark_safe(
                    error_template.render({
                        'conflicts': conflicts
                    })
                )
            )


class ReferenceDataRecordUploadForm(forms.Form):
    file = forms.FileField(
        label='CSV file',
        required=True,
        validators=[validators.FileExtensionValidator(allowed_extensions=['csv'])]
    )

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop('reference_dataset')
        super().__init__(*args, **kwargs)

    def clean_file(self):
        reader = csv.DictReader(chunk.decode() for chunk in self.cleaned_data['file'])
        csv_fields = [x.lower() for x in reader.fieldnames]
        dataset_fields = [x.lower() for x in self.reference_dataset.field_names]
        if sorted(csv_fields) != sorted(dataset_fields):
            raise ValidationError(
                'Please ensure the uploaded csv file headers match the target reference dataset columns'
            )
        return self.cleaned_data['file']


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
