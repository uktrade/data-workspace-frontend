import csv
import uuid

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.core import validators
from django.db import transaction, models
from django.db.models import Q
from django.forms.widgets import SelectMultiple
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from adminsortable2.admin import CustomInlineFormSet
from django_better_admin_arrayfield.forms.fields import DynamicArrayField

from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    SensitivityType,
    SourceLink,
    DataSet,
    DataSetVisualisation,
    ReferenceDatasetField,
    CustomDatasetQuery,
    DataCutDataset,
    SourceView,
    SourceTable,
    MasterDataset,
    VisualisationCatalogueItem,
    VisualisationLink,
)
from dataworkspace.datasets_db import extract_queried_tables_from_sql_query


class AutoCompleteUserFieldsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Do not allow adding/editing users for autocomplete fields
        for field in (
            "enquiries_contact",
            "information_asset_owner",
            "information_asset_manager",
        ):
            if field in self.fields:
                self.fields[field].widget.can_add_related = False
                self.fields[field].widget.can_change_related = False
                self.fields[field].widget.can_delete_related = False


class ReferenceDatasetForm(AutoCompleteUserFieldsMixin, forms.ModelForm):
    sensitivity = forms.ModelMultipleChoiceField(
        queryset=SensitivityType.objects.all(), widget=forms.CheckboxSelectMultiple, required=False
    )

    information_asset_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="info_asset_owned_reference_datasets",
        null=True,
        blank=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "information_asset_owner" in self.fields:
            self.fields["information_asset_owner"].required = True
        if "information_asset_manager" in self.fields:
            self.fields["information_asset_manager"].required = True
        if "enquiries_contact" in self.fields:
            self.fields["enquiries_contact"].required = True
        if "sort_field" in self.fields and self.instance.pk is not None:
            self.fields["sort_field"].queryset = self.instance.fields.all()


class ReferenceDataInlineFormset(CustomInlineFormSet):
    model = ReferenceDatasetField

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs.update({"parent": self.instance})
        return kwargs

    def _get_all_values_for_field(self, field):
        """
        Return the value for `field` in all related forms
        :param field:
        :return:
        """
        return [
            x.cleaned_data[field]
            for x in self.forms
            if x.cleaned_data.get(field) and not x.cleaned_data.get("DELETE")
        ]

    def clean(self):
        # Ensure one and only one field is set as identifier
        identifiers = self._get_all_values_for_field("is_identifier")
        if not identifiers:
            raise forms.ValidationError("Please ensure one field is set as the unique identifier")
        if len(identifiers) > 1:
            raise forms.ValidationError("Please select only one unique identifier field")

        # Ensure column names don't clash
        column_names = self._get_all_values_for_field("column_name")
        if len(column_names) != len(set(column_names)):
            raise forms.ValidationError("Please ensure column names are unique")

        # Ensure field names are not duplicated
        names = self._get_all_values_for_field("name")
        if len(names) != len(set(names)):
            raise forms.ValidationError("Please ensure field names are unique")

        # Ensure one and only one field is set as the display name field
        display_names = self._get_all_values_for_field("is_display_name")
        if not display_names:
            raise forms.ValidationError("Please ensure one field is set as the display name")
        if len(display_names) > 1:
            raise forms.ValidationError("Please select only one display name field")

        # Ensure column names dont clash with relationship names
        if set(column_names) & set(self._get_all_values_for_field("relationship_name")):
            raise forms.ValidationError(
                "Please ensure column names do not clash with relationship names"
            )

        # Ensure fields with the same relationship name point to the same underlying dataset
        relationships = {}
        for form in self.forms:
            if not form.cleaned_data.get("relationship_name", None) or not form.is_valid():
                continue

            relationship_name = form.cleaned_data["relationship_name"]
            if relationship_name not in relationships:
                relationships[relationship_name] = form.cleaned_data[
                    "linked_reference_dataset_field"
                ].reference_dataset
            else:
                if (
                    relationships[relationship_name]
                    != form.cleaned_data["linked_reference_dataset_field"].reference_dataset
                ):
                    raise forms.ValidationError(
                        "Fields with the same relationship name must point to the same underlying reference dataset"
                    )


class ReferenceDataFieldInlineForm(forms.ModelForm):
    _reserved_column_names = (
        "id",
        "reference_dataset",
        "reference_dataset_id",
        "updated_date",
    )
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": "1"}))

    class Meta:
        model = ReferenceDatasetField
        fields = (
            "name",
            "column_name",
            "data_type",
            "linked_reference_dataset_field",
            "description",
            "is_identifier",
            "sort_order",
        )

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)

        if self.instance.id is not None:
            # Do not allow changing the data type of a foreign key
            if self.instance.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                self.fields["data_type"].disabled = True
            # Disable the relationship selector if the data type is not foreign key
            elif self.fields["linked_reference_dataset_field"].initial is None:
                self.fields["linked_reference_dataset_field"].disabled = True
                self.fields["linked_reference_dataset_field"].queryset = (
                    ReferenceDatasetField.objects.none()
                )
            self.fields["column_name"].disabled = True
            self.fields["relationship_name"].disabled = True

        if (
            self.instance.id is None
            or self.instance.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
        ):
            # Only allow linking to fields that:
            #   1. Do not belong to this reference dataset
            #   2. Are from a non-deleted reference dataset
            #   3. Are not, themselves, linked dataset fields
            #   4. Do not contain links back to this reference dataset
            fields = ReferenceDatasetField.objects.exclude(
                Q(reference_dataset=self.reference_dataset)
                | Q(reference_dataset__deleted=True)
                | Q(data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY)
            )

            # Hide all fields from reference datasets that have a linked field
            # pointing to a field in the current dataset (circular link)
            circular_reference_datasets_fields = []
            if self.reference_dataset.id:
                circular_reference_datasets = fields.filter(
                    linked_reference_dataset_field__reference_dataset=self.reference_dataset
                ).values_list("reference_dataset_id", flat=True)
                circular_reference_datasets_fields = fields.filter(
                    reference_dataset_id__in=circular_reference_datasets
                ).values_list("id", flat=True)

            fields = fields.exclude(id__in=circular_reference_datasets_fields)

            self.fields["linked_reference_dataset_field"].choices = [
                ("", "---------"),
            ] + [(field.id, str(field)) for field in fields]

        # Hide the linked dataset add/edit buttons on the inline formset
        self.fields["linked_reference_dataset_field"].widget.can_add_related = False
        self.fields["linked_reference_dataset_field"].widget.can_change_related = False
        self.fields["linked_reference_dataset_field"].widget.can_delete_related = False

    def clean_linked_reference_dataset_field(self):
        cleaned = self.cleaned_data

        if cleaned.get("data_type") == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
            # Ensure a reference dataset to link to was provided
            if cleaned.get("linked_reference_dataset_field") is None:
                raise forms.ValidationError("Please select a reference data set field to link to")

            # Ensure a reference dataset field cannot link to it's own parent
            if (
                self.reference_dataset
                == cleaned["linked_reference_dataset_field"].reference_dataset
            ):
                raise forms.ValidationError("A reference dataset record cannot point to itself")

            # Ensure a reference dataset field cannot link to a field that is itself linked
            # to another reference dataset field
            if (
                cleaned["linked_reference_dataset_field"].data_type
                == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            ):
                raise forms.ValidationError(
                    "A reference dataset field cannot point to another field that is itself linked"
                )

            # Ensure a reference dataset field cannot link to a field in a dataset that has a
            # linked field pointing to a field in the current dataset (circular link)
            if self.reference_dataset.id:
                circular_reference_datasets = ReferenceDatasetField.objects.filter(
                    data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                    linked_reference_dataset_field__reference_dataset=self.reference_dataset,
                ).values_list("reference_dataset_id", flat=True)
                if (
                    cleaned["linked_reference_dataset_field"].reference_dataset.id
                    in circular_reference_datasets
                ):
                    raise forms.ValidationError(
                        "A reference dataset field cannot point to another field that points back "
                        "to this dataset (circular link)"
                    )

            # If this reference dataset syncs with an external database we need
            # to ensure any linked fields also sync with the same database
            ext_db = self.reference_dataset.external_database
            linked_ext_db = cleaned[
                "linked_reference_dataset_field"
            ].reference_dataset.external_database
            if ext_db is not None and ext_db != linked_ext_db:
                raise forms.ValidationError(
                    "Linked reference dataset does not exist on external database {}".format(
                        ext_db.memorable_name
                    )
                )

        return cleaned["linked_reference_dataset_field"]

    def clean_data_type(self):
        orig_data_type = self.instance.data_type
        new_data_type = self.cleaned_data["data_type"]

        if self.instance.id is not None:
            # Do not allow changing from foreign key to another data type
            if (
                new_data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
                and orig_data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            ):
                raise forms.ValidationError("Linked reference dataset data type cannot be updated")

            # Do not allow changing from another data type to foreign key
            if (
                new_data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
                and orig_data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            ):
                raise forms.ValidationError(
                    "Data type cannot be changed to linked reference dataset"
                )

            # Do not allow users to change the data type of a column
            # if that column has existing data.
            if new_data_type != orig_data_type:
                matching_records = self.instance.reference_dataset.get_records().exclude(
                    **{self.instance.column_name: None}
                )
                if matching_records.exists():
                    raise forms.ValidationError(
                        "Unable to change data type when data exists in column"
                    )

        return new_data_type

    def clean_is_identifier(self):
        cleaned = self.cleaned_data
        # Do not allow a foreign key field to be set as an identifier
        if (
            cleaned.get("is_identifier")
            and cleaned.get("data_type") == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
        ):
            raise forms.ValidationError("Identifier field cannot be linked reference data type")
        return cleaned.get("is_identifier")

    def clean_column_name(self):
        cleaned = self.cleaned_data
        column_name = cleaned["column_name"]
        if column_name in self._reserved_column_names:
            raise forms.ValidationError(
                '"{}" is a reserved column name (along with: "{}")'.format(
                    column_name,
                    '", "'.join([x for x in self._reserved_column_names if x != column_name]),
                )
            )

        # Saving a dataset with no fields results in data_type not being
        # included in the cleaned data as its a mandatory field
        if not cleaned.get("data_type"):
            return column_name

        if not column_name and cleaned["data_type"] != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
            raise forms.ValidationError("This field type must have a column name")
        if column_name and cleaned["data_type"] == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
            raise forms.ValidationError("This field type cannot have a column name")
        return column_name

    def clean_relationship_name(self):
        cleaned = self.cleaned_data
        relationship_name = cleaned["relationship_name"]

        if relationship_name in self._reserved_column_names:
            raise forms.ValidationError(
                '"{}" is a reserved column name (along with: "{}")'.format(
                    relationship_name,
                    '", "'.join(
                        [x for x in self._reserved_column_names if x != relationship_name]
                    ),
                )
            )

        # Saving a dataset with no fields results in data_type not being
        # included in the cleaned data as its a mandatory field
        if not cleaned.get("data_type"):
            return relationship_name

        if (
            not relationship_name
            and cleaned["data_type"] == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
        ):
            raise forms.ValidationError("This field type must have a relationship name")
        if (
            relationship_name
            and cleaned["data_type"] != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
        ):
            raise forms.ValidationError("This field type cannot have a relationship name")
        return relationship_name

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        if (
            cleaned["data_type"] != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
            and self.cleaned_data["linked_reference_dataset_field"]
        ):
            self.add_error(
                "data_type",
                forms.ValidationError(
                    "Please select the Linked Reference Dataset Field data type"
                ),
            )
        return cleaned


class ReferenceDataRowDeleteForm(forms.Form):
    id = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop("reference_dataset")
        super().__init__(*args, **kwargs)

    def clean(self):
        # Do not allow deletion of records that are linked to by other records
        linking_fields = ReferenceDatasetField.objects.filter(
            linked_reference_dataset_field__reference_dataset=self.reference_dataset
        )

        conflicts = []
        for field in linking_fields:
            conflicts += field.reference_dataset.get_records().filter(
                **{"{}__id".format(field.relationship_name): self.cleaned_data.get("id")}
            )

        if conflicts:
            error_template = get_template("admin/inc/delete_linked_to_record_error.html")
            raise forms.ValidationError(mark_safe(error_template.render({"conflicts": conflicts})))


class ReferenceDataRowDeleteAllForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop("reference_dataset")
        super().__init__(*args, **kwargs)

    def clean(self):
        # Do not allow deletion of records that are linked to by other records
        linking_fields = ReferenceDatasetField.objects.filter(
            linked_reference_dataset_field__reference_dataset=self.reference_dataset
        )

        conflicts = []
        for field in linking_fields:
            for record in self.reference_dataset.get_records():
                conflicts += field.reference_dataset.get_records().filter(
                    **{"{}__id".format(field.relationship_name): record.id}
                )

        if conflicts:
            error_template = get_template("admin/inc/delete_all_linked_to_record_error.html")
            raise forms.ValidationError(mark_safe(error_template.render({"conflicts": conflicts})))


class ReferenceDataRecordUploadForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        required=True,
        validators=[validators.FileExtensionValidator(allowed_extensions=["csv"])],
    )

    def __init__(self, *args, **kwargs):
        self.reference_dataset = kwargs.pop("reference_dataset")
        super().__init__(*args, **kwargs)

    def clean_file(self):
        reader = csv.DictReader(chunk.decode("utf-8-sig") for chunk in self.cleaned_data["file"])
        csv_fields = [x.lower() for x in reader.fieldnames]
        for field in [
            (
                field.name.lower()
                if field.data_type != field.DATA_TYPE_FOREIGN_KEY
                else field.relationship_name_for_record_forms.lower()
            )
            for _, field in self.reference_dataset.editable_fields.items()
        ]:
            if field not in csv_fields:
                raise forms.ValidationError(
                    "Please ensure the uploaded csv file headers include "
                    "all the target reference dataset columns"
                )
        return self.cleaned_data["file"]


def clean_identifier(form):
    """
    Helper function for validating dynamically created reference dataset identifier field.
    Checks that supplied identifier value is unique for this reference data set
    :param form:
    :return:
    """
    field = form.instance
    reference_dataset = form.cleaned_data["reference_dataset"]
    id_field = reference_dataset.identifier_field.column_name
    cleaned_data = form.cleaned_data
    if id_field in cleaned_data:
        exists = (
            reference_dataset.get_records()
            .filter(**{id_field: cleaned_data[id_field]})
            .exclude(id=field.id)
        )
        if exists:
            raise forms.ValidationError("A record with this identifier already exists")
    return cleaned_data[id_field]


class BaseDatasetForm(AutoCompleteUserFieldsMixin, forms.ModelForm):
    type = forms.HiddenInput()
    eligibility_criteria = DynamicArrayField(base_field=forms.CharField(), required=False)
    request_approvers = DynamicArrayField(base_field=forms.CharField(), required=False)
    authorized_users = forms.ModelMultipleChoiceField(
        required=False,
        widget=FilteredSelectMultiple("users", False),
        queryset=get_user_model().objects.filter().order_by("email"),
    )
    sensitivity = forms.ModelMultipleChoiceField(
        queryset=SensitivityType.objects.all(), widget=forms.CheckboxSelectMultiple, required=False
    )

    # Invalid dataset type - must be overridden by the subclass.
    dataset_type = -1
    can_change_user_permission_codename = None

    class Meta:
        model = DataSet
        fields = "__all__"
        widgets = {"type": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        kwargs["initial"] = {"type": self.dataset_type}
        super().__init__(*args, **kwargs)
        is_instance = "instance" in kwargs and kwargs["instance"]

        self.fields["authorized_users"].initial = (
            get_user_model().objects.filter(datasetuserpermission__dataset=kwargs["instance"])
            if is_instance
            else get_user_model().objects.none()
        )
        if not user.is_superuser and not user.has_perm(self.can_change_user_permission_codename):
            self.fields["user_access_type"].disabled = True

            self.fields["authorized_users"].disabled = True
            self.fields["authorized_users"].widget = SelectMultiple(
                choices=(
                    (user.id, user.email)
                    for user in self.fields["authorized_users"].queryset.all()
                )
            )


class DataCutDatasetForm(BaseDatasetForm):
    dataset_type = DataSetType.DATACUT
    can_change_user_permission_codename = "datasets.change_datacutuserpermission"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["information_asset_owner"].required = True
        self.fields["information_asset_manager"].required = True
        self.fields["enquiries_contact"].required = True

    class Meta:
        model = MasterDataset
        fields = "__all__"


class MasterDatasetForm(BaseDatasetForm):
    dataset_type = DataSetType.MASTER
    can_change_user_permission_codename = "datasets.change_masterdatasetuserpermission"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["information_asset_owner"].required = True
        self.fields["information_asset_manager"].required = True
        self.fields["enquiries_contact"].required = True

    class Meta:
        model = MasterDataset
        fields = "__all__"


class SourceLinkForm(forms.ModelForm):
    class Meta:
        fields = ("name", "url", "format", "frequency")
        model = SourceLink


class SourceLinkUploadForm(forms.ModelForm):
    file = forms.FileField(required=True)

    class Meta:
        model = SourceLink
        fields = ("dataset", "name", "format", "frequency", "file")
        widgets = {"dataset": forms.HiddenInput()}


class CustomDatasetQueryForm(forms.ModelForm):
    model = CustomDatasetQuery

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = DataCutDataset.objects.live()


class CustomDatasetQueryInlineForm(forms.ModelForm):
    model = CustomDatasetQuery

    def clean(self):
        super().clean()

        if (
            self.cleaned_data.get("reviewed") is False
            and self.cleaned_data["dataset"].published is True
        ):
            raise forms.ValidationError(
                {"reviewed": "You must review this SQL query before the dataset can be published."}
            )

        if self.instance.reviewed is True and self.cleaned_data["dataset"].published is False:
            if set(self.changed_data) - {"reviewed"}:
                self.cleaned_data["reviewed"] = False

                # We need to also update the instance directly, as well, because the `reviewed` field will not otherwise
                # be updated for users who have `reviewed` as a read-only field (i.e. "Subject Matter Experts").
                self.instance.reviewed = False

        return self.cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        # Lock the row to prevent race conditions that can happen if another user
        # tries to update the same query at the same time. This prevents potential
        # duplicate or mismatching CustomDatasetQueryTable objects.
        if self.instance.pk:
            CustomDatasetQuery.objects.select_for_update().get(id=self.instance.pk)

        instance = super().save(commit)

        tables = extract_queried_tables_from_sql_query(instance.query)

        # Save the extracted tables in a seperate model for later user
        instance.tables.all().delete()
        for t in tables:
            instance.tables.create(schema=t[0], table=t[1])
        return instance


class SourceViewForm(forms.ModelForm):
    model = SourceView

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = DataCutDataset.objects.live()


class DataSetVisualisationForm(forms.ModelForm):
    model = DataSetVisualisation


class SourceTableForm(forms.ModelForm):
    model = SourceTable

    class Meta:
        fields = (
            "dataset",
            "name",
            "database",
            "schema",
            "frequency",
            "table",
            "dataset_finder_opted_in",
            "data_grid_enabled",
            "data_grid_download_enabled",
            "data_grid_download_limit",
            "disable_data_grid_interaction",
            "published",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dataset"].queryset = MasterDataset.objects.live()

    def clean(self):
        cleaned = self.cleaned_data
        grid_enabled = cleaned.get("data_grid_enabled", False)
        download_enabled = cleaned.get("data_grid_download_enabled", False)
        download_limit = cleaned.get("data_grid_download_limit", None)

        if not grid_enabled and (download_enabled or download_limit):
            raise forms.ValidationError(
                {"data_grid_enabled": "Grid must be enabled for download settings to take effect"}
            )

        if download_enabled and not download_limit:
            raise forms.ValidationError(
                {
                    "data_grid_download_limit": "A download limit must be set if downloads are enabled"
                }
            )

        return cleaned


class VisualisationCatalogueItemForm(AutoCompleteUserFieldsMixin, forms.ModelForm):
    eligibility_criteria = DynamicArrayField(base_field=forms.CharField(), required=False)
    request_approvers = DynamicArrayField(base_field=forms.CharField(), required=False)
    authorized_users = forms.ModelMultipleChoiceField(
        required=False,
        widget=FilteredSelectMultiple("users", False),
        queryset=get_user_model().objects.filter().order_by("email"),
    )
    can_change_user_permission_codename = "datasets.change_visualisationuserpermission"
    sensitivity = forms.ModelMultipleChoiceField(
        queryset=SensitivityType.objects.all(), widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = VisualisationCatalogueItem
        fields = "__all__"
        widgets = {"type": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        is_instance = "instance" in kwargs and kwargs["instance"]

        self.fields["authorized_users"].initial = (
            get_user_model().objects.filter(
                visualisationuserpermission__visualisation=kwargs["instance"]
            )
            if is_instance
            else get_user_model().objects.none()
        )
        if not user.is_superuser and not user.has_perm(self.can_change_user_permission_codename):
            self.fields["user_access_type"].disabled = True

            self.fields["authorized_users"].disabled = True
            self.fields["authorized_users"].widget = SelectMultiple(
                choices=(
                    (user.id, user.email)
                    for user in self.fields["authorized_users"].queryset.all()
                )
            )

        self.fields["information_asset_owner"].required = True
        self.fields["information_asset_manager"].required = True
        self.fields["enquiries_contact"].required = True


class VisualisationLinkForm(forms.ModelForm):
    class Meta:
        fields = ("visualisation_type", "name", "identifier")
        model = VisualisationLink

    def clean_identifier(self):
        cleaned = self.cleaned_data
        identifier = cleaned.get("identifier")

        visualisation_type = cleaned.get("visualisation_type", None)
        if not visualisation_type:
            return identifier

        if visualisation_type == "QUICKSIGHT":
            try:
                uuid.UUID(identifier)
            except ValueError:
                # pylint: disable=raise-missing-from
                raise forms.ValidationError("Quicksight identifiers must be a UUID.")

        return identifier
