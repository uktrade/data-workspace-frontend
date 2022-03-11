from functools import partial
import inspect
import sys
import mock

from botocore.exceptions import ClientError

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import Client
import pytest

from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.datasets.models import (
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    ReferenceDatasetUploadLogRecord,
    ReferenceDatasetUploadLog,
    DataSet,
    CustomDatasetQuery,
    SourceTable,
)
from dataworkspace.apps.explorer.utils import get_user_explorer_connection_settings
from dataworkspace.tests import factories
from dataworkspace.tests.common import BaseAdminTestCase, get_http_sso_data


class TestCustomAdminSite(BaseAdminTestCase):
    def test_non_admin_access(self):
        # Ensure non-admins get a 404 page
        self.user.is_staff = False
        self.user.is_superuser = False
        self.user.save()
        response = self._authenticated_get(reverse("admin:login"))
        # pylint: disable=no-member
        self.assertEqual(response.status_code, 404)

    def test_admin_access(self):
        # Ensure admins are able to view the admin site
        response = self._authenticated_get(reverse("admin:login"))
        # pylint: disable=no-member
        self.assertEqual(response.status_code, 302)


class TestReferenceDatasetAdmin(BaseAdminTestCase):
    databases = ["default", "test_external_db"]

    def test_create_reference_dataset_no_fields(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 0,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
            },
        )
        self.assertContains(response, "Please ensure one field is set as the unique identifier")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_no_identifiers(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 1,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": 1,
                "fields-0-reference_dataset": 1,
                "fields-0-name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
            },
        )
        self.assertContains(response, "Please ensure one field is set as the unique identifier")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_multiple_identifiers(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
                "fields-1-is_identifier": "on",
            },
        )
        self.assertContains(response, "Please select only one unique identifier field")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_data_type(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field",
                "fields-1-data_type": 2,
                "fields-1-description": "Another field",
                "fields-1-linked_reference_dataset_field": reference_dataset.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(response, "Please select the Linked Reference Dataset Field data type")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_duplicate_column_names(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(response, "Please ensure column names are unique")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_clashing_column_and_relationship_names(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "field2",
                "fields-1-relationship_name": "field",
                "fields-1-data_type": 8,
                "fields-1-description": "Another field",
                "fields-1-linked_reference_dataset_field": reference_dataset.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(
            response, "Please ensure column names do not clash with relationship names"
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_relationship_name_with_different_datasets(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )

        reference_dataset_2 = self._create_reference_dataset(name="foo", table_name="ref_foo")
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset_2, data_type=1, is_identifier=True
        )

        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "field2",
                "fields-1-relationship_name": "rel",
                "fields-1-data_type": 8,
                "fields-1-description": "Another field",
                "fields-1-linked_reference_dataset_field": reference_dataset.fields.get(
                    is_identifier=True
                ).id,
                "fields-2-name": "field3",
                "fields-2-relationship_name": "rel",
                "fields-2-data_type": 8,
                "fields-2-description": "Another field",
                "fields-2-linked_reference_dataset_field": reference_dataset_2.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(
            response,
            "Fields with the same relationship name must point to the same underlying reference dataset",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_duplicate_names(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field1",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(response, "Please ensure field names are unique")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_column_name(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1 test",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(
            response,
            "Column names must be lowercase and must start with a letter and contain "
            "only letters, numbers, underscores and full stops.",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_relationship_name(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-relationship_name": "field2 test",
                "fields-1-data_type": 8,
                "fields-1-description": "Another field",
                "fields-1-linked_reference_dataset_field": reference_dataset.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(
            response,
            "Relationship names must start with a letter and contain only "
            "letters, numbers, underscores and full stops.",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_field_type_column_name(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 8,
                "fields-1-description": "Another field",
                "fields-1-linked_reference_dataset_field": reference_dataset.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        # field 1 error
        self.assertContains(
            response,
            "This field type must have a column name",
        )
        # field 2 error
        self.assertContains(
            response,
            "This field type cannot have a column name",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_field_type_relationship_name(self):
        reference_dataset = self._create_reference_dataset()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-data_type": 8,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-relationship_name": "field2",
                "fields-1-data_type": 2,
                "fields-1-description": "Another field",
            },
        )
        # field 1 error
        self.assertContains(
            response,
            "This field type must have a relationship name",
        )
        # field 2 error
        self.assertContains(
            response,
            "This field type cannot have a relationship name",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_existing_table_name(self):
        self._create_reference_dataset()
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test_dataset",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(response, "Reference dataset with this Table name already exists.")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_invalid_table_name(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "test_dataset",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(
            response,
            "Table names must be prefixed with &quot;ref_&quot; "
            "and can contain only lowercase letters, numbers and underscores",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_uppercase_table_name(self):
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_UPPERCASE",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(
            response,
            "Table names must be prefixed with &quot;ref_&quot; "
            "and can contain only lowercase letters, numbers and underscores",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_create_reference_dataset_valid(self):
        ref_dataset_slug = "test-ref-1"
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test ref 1",
                "table_name": "ref_test_create_ref_dataset_valid",
                "slug": ref_dataset_slug,
                "external_database": "",
                "short_description": "test description that is short",
                "description": "test description",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": "",
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": 2,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "field2",
                "fields-1-column_name": "field2",
                "fields-1-data_type": 1,
                "fields-1-description": "Another field",
            },
        )
        self.assertContains(response, "was added successfully")
        self.assertEqual(num_datasets + 1, ReferenceDataset.objects.count())
        ref_dataset = ReferenceDataset.objects.get(slug=ref_dataset_slug)
        self.assertEqual(ref_dataset.description, "test description")

    def test_edit_reference_dataset_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=2
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": "updated_field_2",
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-2-reference_dataset": reference_dataset.id,
                "fields-2-name": "Added field 1",
                "fields-2-column_name": "Added field 1",
                "fields-2-data_type": 3,
                "fields-2-description": "Added field",
            },
        )
        self.assertContains(response, "Please select only one unique identifier field")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_display_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=2
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": "updated_field_2",
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_display_name": "on",
                "fields-2-reference_dataset": reference_dataset.id,
                "fields-2-name": "Added field 1",
                "fields-2-column_name": "Added field 1",
                "fields-2-data_type": 3,
                "fields-2-description": "Added field",
            },
        )
        self.assertContains(response, "Please select only one display name field")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_column_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": 1,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": field1.column_name,
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-2-reference_dataset": reference_dataset.id,
                "fields-2-name": "Added field 1",
                "fields-2-column_name": "added_field_1",
                "fields-2-data_type": 3,
                "fields-2-description": "Added field",
            },
        )
        self.assertContains(response, "Please ensure column names are unique")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_invalid_column_name(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            column_name="field_1",
        )
        field2 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset, data_type=2, column_name="field_2"
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": "field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": "a space",
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-2-reference_dataset": reference_dataset.id,
                "fields-2-name": "Added field 1",
                "fields-2-column_name": "added_field_1",
                "fields-2-data_type": 3,
                "fields-2-description": "Added field",
            },
        )
        self.assertContains(
            response,
            "Column names must be lowercase and must start with a letter and contain "
            "only letters, numbers, underscores and full stops.",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_duplicate_names(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            column_name="field_1",
            name="field",
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test ref 1",
                "table_name": "ref_test1",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": field1.id,
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": field1.name,
                "fields-0-column_name": "field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": field1.name,
                "fields-1-column_name": "field_2",
                "fields-1-data_type": 3,
                "fields-1-description": "Added field",
            },
        )
        self.assertContains(response, "Please ensure field names are unique")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

    def test_edit_reference_dataset_update_column_names(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            column_name="field_1",
            description="field 1 description",
        )
        num_datasets = ReferenceDataset.objects.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": reference_dataset.name,
                "table_name": reference_dataset.table_name,
                "slug": reference_dataset.slug,
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 1,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": str(field1.id),
                "fields-0-reference_dataset": str(reference_dataset.id),
                "fields-0-name": field1.name,
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 1,
                "fields-0-description": "updated description",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())

        # column_name field is disabled so post value is ignored
        field1.refresh_from_db()
        self.assertEqual(field1.column_name, "field_1")
        self.assertEqual(field1.description, "updated description")

    def test_edit_reference_dataset_change_table_name(self):
        # Ensure that the table name cannot be changed via the admin
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            description="test",
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=2,
            is_identifier=False,
            description="test",
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        original_table_name = reference_dataset.table_name
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": reference_dataset.name,
                "table_name": "ref_test_updated",
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": reference_dataset.short_description,
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": field1.id,
                "sort_direction": ReferenceDataset.SORT_DIR_ASC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": field1.name,
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": field1.data_type,
                "fields-0-description": field2.description,
                "fields-0-is_identifier": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": field2.name,
                "fields-1-column_name": field2.column_name,
                "fields-1-data_type": field2.data_type,
                "fields-1-description": field2.description,
                "fields-1-is_display_name": "on",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())
        self.assertEqual(
            ReferenceDataset.objects.get(pk=reference_dataset.id).table_name,
            original_table_name,
        )

    def test_edit_reference_dataset_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=2, is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "table_name": "ref_test_updated",
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": "",
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 3,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_display_name": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": field2.column_name,
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-2-reference_dataset": reference_dataset.id,
                "fields-2-name": "added_field_1",
                "fields-2-column_name": "added_field_1",
                "fields-2-data_type": 3,
                "fields-2-description": "Added field 1",
                "fields-__prefix__-reference_dataset": reference_dataset.id,
                "_continue": "Save and continue editing",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields + 1, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_field(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=2, is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": field2.column_name,
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-1-DELETE": "on",
            },
        )
        self.assertContains(response, "Please ensure one field is set as the unique identifier")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_all_fields(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=2, is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "slug": "test-ref-1",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-0-DELETE": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": "updated_field_2",
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-1-DELETE": "on",
            },
        )
        self.assertContains(response, "Please ensure one field is set as the unique identifier")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_delete_reference_dataset_identifier_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=2, is_identifier=False
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "table_name": reference_dataset.table_name,
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": field2.id,
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-DELETE": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": field2.column_name,
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-1-is_display_name": "on",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields - 1, reference_dataset.fields.count())

    def test_reference_data_record_create_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name="field1",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name="field2",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=False,
        )
        reference_dataset.save_record(
            None,
            {
                "reference_dataset": reference_dataset,
                field1.column_name: 1,
                field2.column_name: "record1",
            },
        )
        num_records = len(reference_dataset.get_records())
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-add", args=(reference_dataset.id,)),
            {
                "reference_dataset": reference_dataset.id,
                field1.column_name: 1,
                field2.column_name: "record2",
            },
        )
        self.assertContains(response, "A record with this identifier already exists")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_create_missing_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name="field1",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name="field2",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=False,
        )
        reference_dataset.save_record(
            None,
            {
                "reference_dataset": reference_dataset,
                field1.column_name: 1,
                field2.column_name: "record1",
            },
        )
        num_records = len(reference_dataset.get_records())
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-add", args=(reference_dataset.id,)),
            {
                "reference_dataset": reference_dataset.id,
                field1.column_name: "",
                field2.column_name: "record2",
            },
        )
        self.assertContains(response, "This field is required")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_invalid_datatypes(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name="field1",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        url = reverse("dw-admin:reference-dataset-record-add", args=(reference_dataset.id,))
        num_records = len(reference_dataset.get_records())

        # Int
        response = self._authenticated_post(url, {field.column_name: "a string"})
        self.assertContains(response, "Enter a whole number.")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Float
        field.data_type = ReferenceDatasetField.DATA_TYPE_FLOAT
        field.save()
        response = self._authenticated_post(url, {field.column_name: "a string"})
        self.assertContains(response, "Enter a number.")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Date
        field.data_type = ReferenceDatasetField.DATA_TYPE_DATE
        field.save()
        response = self._authenticated_post(url, {field.column_name: "a string"})
        self.assertContains(response, "Enter a valid date.")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Datetime
        field.data_type = ReferenceDatasetField.DATA_TYPE_DATETIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: "a string"})
        self.assertContains(response, "Enter a valid date/time.")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

        # Time
        field.data_type = ReferenceDatasetField.DATA_TYPE_TIME
        field.save()
        response = self._authenticated_post(url, {field.column_name: "a string"})
        self.assertContains(response, "Enter a valid time.")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_create(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name="char",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name="int",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name="float",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name="date",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name="time",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name="datetime",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name="bool",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_BOOLEAN,
        )
        num_records = len(reference_dataset.get_records())
        fields = {
            "reference_dataset": reference_dataset.id,
            field1.column_name: "test1",
            field2.column_name: 1,
            field3.column_name: 2.0,
            field4.column_name: "2019-01-02",
            field5.column_name: "11:11:00",
            field6.column_name: "2019-05-25 14:30:59",
            field7.column_name: True,
        }
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-add", args=(reference_dataset.id,)),
            fields,
        )
        self.assertContains(response, "Reference dataset record added successfully")
        self.assertEqual(num_records + 1, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(1)
        del fields["reference_dataset"]
        fields[field6.column_name] += "+00:00"
        for k, v in fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_edit_duplicate_identifier(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name="id",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(
            None, {"reference_dataset": reference_dataset, field.column_name: 1}
        )
        reference_dataset.save_record(
            None, {"reference_dataset": reference_dataset, field.column_name: 2}
        )
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records()[0]
        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-edit",
                args=(reference_dataset.id, record.id),
            ),
            {"reference_dataset": reference_dataset.id, field.column_name: 2},
        )
        self.assertContains(response, "A record with this identifier already exists")
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_edit_valid(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            name="char",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            name="int",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            name="float",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_FLOAT,
        )
        field4 = factories.ReferenceDatasetFieldFactory.create(
            name="date",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATE,
        )
        field5 = factories.ReferenceDatasetFieldFactory.create(
            name="time",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_TIME,
        )
        field6 = factories.ReferenceDatasetFieldFactory.create(
            name="datetime",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_DATETIME,
        )
        field7 = factories.ReferenceDatasetFieldFactory.create(
            name="bool",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_BOOLEAN,
        )
        reference_dataset.save_record(
            None,
            {
                "reference_dataset": reference_dataset,
                field1.column_name: "test1",
                field2.column_name: 1,
                field3.column_name: 2.0,
                field4.column_name: "2019-01-02",
                field5.column_name: "11:11:00",
                field6.column_name: "2019-01-01 01:00:01",
                field7.column_name: True,
            },
        )
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records().first()
        update_fields = {
            "reference_dataset": reference_dataset.id,
            field1.column_name: "updated-char",
            field2.column_name: 99,
            field3.column_name: 1.0,
            field4.column_name: "2017-03-22",
            field5.column_name: "23:23:00",
            field6.column_name: "2019-05-25 14:30:59",
            field7.column_name: True,
        }
        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-edit",
                args=(reference_dataset.id, record.id),
            ),
            update_fields,
        )
        self.assertContains(response, "Reference dataset record updated successfully")
        self.assertEqual(num_records, len(reference_dataset.get_records()))
        record = reference_dataset.get_record_by_custom_id(99)
        del update_fields["reference_dataset"]
        update_fields[field6.column_name] += "+00:00"
        for k, v in update_fields.items():
            self.assertEqual(str(getattr(record, k)), str(v))

    def test_reference_data_record_delete_confirm(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name="field1",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(
            None, {"reference_dataset": reference_dataset, field.column_name: 1}
        )
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records().first()
        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-delete",
                args=(reference_dataset.id, record.id),
            )
        )
        self.assertContains(
            response,
            "Are you sure you want to delete the record below from the reference data item",
        )
        self.assertEqual(num_records, len(reference_dataset.get_records()))

    def test_reference_data_record_delete(self):
        reference_dataset = self._create_reference_dataset()
        field = factories.ReferenceDatasetFieldFactory.create(
            name="field1",
            reference_dataset=reference_dataset,
            data_type=ReferenceDatasetField.DATA_TYPE_INT,
            is_identifier=True,
        )
        reference_dataset.save_record(
            None, {"reference_dataset": reference_dataset, field.column_name: 1}
        )
        num_records = len(reference_dataset.get_records())
        record = reference_dataset.get_records()[0]
        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-delete",
                args=(reference_dataset.id, record.id),
            ),
            {"id": record.id},
        )
        self.assertContains(response, "Reference dataset record deleted successfully")
        self.assertEqual(num_records - 1, len(reference_dataset.get_records()))

    def test_create_reference_dataset_link_to_foreign_key(self):
        reference_dataset = self._create_reference_dataset(name="foo", table_name="ref_foo")
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )

        reference_dataset_2 = self._create_reference_dataset(name="bar", table_name="ref_bar")
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset_2, data_type=1, is_identifier=True
        )
        field3 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset_2,
            data_type=8,
            linked_reference_dataset_field=field1,
            relationship_name="rel",
        )

        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "table_name": reference_dataset.table_name,
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": field1.name,
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": field1.data_type,
                "fields-0-is_identifier": "on",
                "fields-1-id": "",
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "a name",
                "fields-1-relationship_name": "a_column",
                "fields-1-data_type": ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                "fields-1-linked_reference_dataset_field": field3.id,
                "fields-1-description": "a description",
            },
        )
        self.assertContains(
            response,
            "A reference dataset field cannot point to another field that is itself linked",
        )
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_create_linked_field_as_foreign_key(self):
        reference_dataset = self._create_reference_dataset()
        linked_dataset = self._create_reference_dataset(
            table_name="test_linked", slug="test-linked"
        )
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset,
            data_type=1,
            is_identifier=True,
            column_name="test",
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_dataset,
            data_type=1,
            is_identifier=True,
            column_name="test",
        )
        num_datasets = ReferenceDataset.objects.count()
        num_fields = reference_dataset.fields.count()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "table_name": reference_dataset.table_name,
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": field1.name,
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": field1.data_type,
                "fields-0-description": "a description",
                "fields-1-id": "",
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "a name",
                "fields-1-relationship_name": "a_column",
                "fields-1-data_type": ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                "fields-1-linked_reference_dataset_field": linked_dataset.fields.get(
                    is_identifier=True
                ).id,
                "fields-1-description": "a description",
                "fields-1-is_identifier": "on",
            },
        )
        self.assertContains(response, "Identifier field cannot be linked reference data type")
        self.assertEqual(num_datasets, ReferenceDataset.objects.count())
        self.assertEqual(num_fields, reference_dataset.fields.count())

    def test_linked_to_dataset_delete(self):
        # Do not allow deletion of a reference dataset if it is linked to by
        # one or more records within other datasets

        # Dynamically built ReferenceDataset record model classes from other
        # tests do not get cleaned up. This causes the delete call to fail as
        # it tries to check for links between the models. Therefore they need
        # to get deleted explicitly
        dataset_model_classes = [
            c[0].lower()
            for c in inspect.getmembers(
                sys.modules["dataworkspace.apps.datasets.models"], inspect.isclass
            )
        ]
        for model in list(apps.all_models["datasets"]):
            # If model is a dynamically created one then delete it
            if model not in dataset_model_classes:
                del apps.all_models["datasets"][model]

        ref_ds1 = self._create_reference_dataset(table_name="test_change_linked_dataset1")
        ref_ds2 = self._create_reference_dataset(table_name="test_change_linked_dataset2")
        self._create_reference_dataset(table_name="test_change_linked_dataset3")
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )

        # Save a record in the linked to dataset
        record = ref_ds2.save_record(None, {"reference_dataset": ref_ds2, "refid": "test"})

        # Save a record in the linked from dataset (linking to the one above)
        ref_ds1.save_record(
            None,
            {
                "reference_dataset": ref_ds1,
                "refid": "another_test",
                "link_id": record.id,
            },
        )

        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_delete", args=(ref_ds2.id,)),
            {"id": ref_ds2.id},
        )
        self.assertContains(
            response,
            "Deleting the Reference dataset 'Test Reference Dataset 1' "
            "would require deleting the following protected related objects",
        )

    def test_delete_linked_to_reference_dataset_record(self):
        # Do not allow deletion of a reference dataset record if it is linked to by
        # one or more records within other datasets
        ref_ds1 = self._create_reference_dataset(table_name="test_change_linked_dataset1")
        ref_ds2 = self._create_reference_dataset(table_name="test_change_linked_dataset2")
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )

        # Save a record in the linked to dataset
        linked_to = ref_ds2.save_record(None, {"reference_dataset": ref_ds2, "refid": "test"})

        # Save a record in the linked from dataset (linking to the record above)
        linked_from = ref_ds1.save_record(
            None,
            {
                "reference_dataset": ref_ds1,
                "refid": "another_test",
                "link_id": linked_to.id,
            },
        )

        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-delete",
                args=(ref_ds2.id, linked_to.id),
            ),
            {"id": linked_from.id},
        )
        self.assertContains(
            response,
            "The record below could not be deleted as it is linked to "
            "by other reference data records",
        )

    def test_delete_all_records(self):
        ref_ds = self._create_reference_dataset(table_name="test_change_linked_dataset1")

        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds,
            data_type=1,
            is_identifier=True,
        )

        ref_ds.save_record(None, {"reference_dataset": ref_ds, "refid": "test"})
        ref_ds.save_record(None, {"reference_dataset": ref_ds, "refid": "test 2"})

        assert len(ref_ds.get_records()) == 2

        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-delete-all",
                args=(ref_ds.id,),
            ),
        )

        assert len(ref_ds.get_records()) == 0
        self.assertContains(
            response,
            "Reference dataset records deleted successfully",
        )

    def test_delete_all_fails_with_linked_reference_dataset_records(self):
        ref_ds1 = self._create_reference_dataset(table_name="test_change_linked_dataset1")
        ref_ds2 = self._create_reference_dataset(table_name="test_change_linked_dataset2")
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )

        # Save a record in the linked to dataset
        linked_to = ref_ds2.save_record(None, {"reference_dataset": ref_ds2, "refid": "test"})

        # Save a record in the linked from dataset (linking to the record above)
        ref_ds1.save_record(
            None,
            {
                "reference_dataset": ref_ds1,
                "refid": "another_test",
                "link_id": linked_to.id,
            },
        )

        assert len(ref_ds2.get_records()) == 1

        response = self._authenticated_post(
            reverse(
                "dw-admin:reference-dataset-record-delete-all",
                args=(ref_ds2.id,),
            ),
        )

        assert len(ref_ds2.get_records()) == 1
        self.assertContains(
            response,
            "The records below could not be deleted as they are linked to "
            "by other reference data records",
        )

    def test_change_linked_reference_dataset(self):
        # If no records with links exist we should be able to edit the ref dataset link
        ref_ds1 = self._create_reference_dataset(table_name="test_change_linked_dataset1")
        ref_ds2 = self._create_reference_dataset(table_name="test_change_linked_dataset2")
        ref_ds3 = self._create_reference_dataset(table_name="test_change_linked_dataset3")
        field1 = ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=1,
            is_identifier=True,
        )
        ReferenceDatasetField.objects.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds3,
            data_type=1,
            is_identifier=True,
        )
        field2 = ReferenceDatasetField.objects.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=8,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )

        # Save a record in the linked to dataset
        ref_ds2.save_record(None, {"reference_dataset": ref_ds2, "refid": "test"})

        # Save a record in the linked from dataset (linking to the one above)
        ref_ds1.save_record(
            None,
            {"reference_dataset": ref_ds1, "refid": "another_test", "link_id": None},
        )

        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(ref_ds1.id,)),
            {
                "id": ref_ds1.id,
                "name": "test updated",
                "table_name": ref_ds1.table_name,
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": "",
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": ref_ds1.id,
                "fields-0-name": field1.name,
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": field1.data_type,
                "fields-0-description": "a description",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": ref_ds1.id,
                "fields-1-name": field2.name,
                "fields-1-relationship_name": field2.relationship_name,
                "fields-1-data_type": field2.data_type,
                "fields-1-linked_reference_dataset_field": ref_ds3.fields.get(
                    is_identifier=True
                ).id,
                "fields-1-description": "test",
            },
        )
        self.assertContains(
            response,
            'The Reference dataset “<a href="/admin/datasets/referencedataset/{}/change/">'
            "test updated</a>” was changed successfully.".format(ref_ds1.id),
            html=True,
        )

    def test_link_to_non_external_dataset(self):
        # Test that a dataset with external db cannot link to a dataset without one
        linked_to = factories.ReferenceDatasetFactory.create()
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_to,
            name="id",
            data_type=2,
            is_identifier=True,
            column_name="extid",
        )
        db = factories.DatabaseFactory.create()
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "test linked non-external",
                "table_name": "ref_test_non_external_dataset_link",
                "slug": "test-ref-link-non-external",
                "external_database": db.id,
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "refid",
                "fields-0-data_type": ReferenceDatasetField.DATA_TYPE_CHAR,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "linked: id",
                "fields-1-relationship_name": "linked",
                "fields-1-data_type": ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                "fields-1-description": "Linked field",
                "fields-1-linked_reference_dataset_field": linked_to.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(
            response,
            "Linked reference dataset does not exist on external database {}".format(
                db.memorable_name
            ),
        )

    def test_link_to_external_dataset(self):
        # Test that a dataset with external db can link to a dataset with one
        db = factories.DatabaseFactory.create()
        linked_to = factories.ReferenceDatasetFactory.create(
            name="linked to", table_name="ext_linked_to", external_database=db
        )
        factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=linked_to,
            name="id",
            data_type=2,
            is_identifier=True,
            column_name="extid",
        )
        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_add"),
            {
                "name": "linked from",
                "table_name": "ref_test_non_external_dataset_link",
                "slug": "test-ref-link-non-external",
                "external_database": db.id,
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": "",
                "sort_direction": ReferenceDataset.SORT_DIR_ASC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 0,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-name": "field1",
                "fields-0-column_name": "field1",
                "fields-0-data_type": ReferenceDatasetField.DATA_TYPE_CHAR,
                "fields-0-description": "A field",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-name": "linked",
                "fields-1-relationship_name": "linked",
                "fields-1-data_type": ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                "fields-1-description": "Linked field",
                "fields-1-linked_reference_dataset_field": linked_to.fields.get(
                    is_identifier=True
                ).id,
            },
        )
        self.assertContains(
            response,
            'The Reference dataset “<a href="/admin/datasets/referencedataset/{}/change/">'
            "linked from</a>” was added successfully.".format(ReferenceDataset.objects.last().id),
            html=True,
        )

    def test_reference_data_record_create_linked(self):
        to_link_ds = self._create_reference_dataset(table_name="to_link_ds")
        factories.ReferenceDatasetFieldFactory.create(
            column_name="identifier",
            reference_dataset=to_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        to_link_record = to_link_ds.save_record(
            None, {"reference_dataset": to_link_ds, "identifier": "a"}
        )

        from_link_ds = self._create_reference_dataset(table_name="from_link_ds")
        factories.ReferenceDatasetFieldFactory.create(
            column_name="identifier",
            reference_dataset=from_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            relationship_name="link",
            reference_dataset=from_link_ds,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=to_link_ds.fields.get(is_identifier=True),
        )

        num_from_records = len(from_link_ds.get_records())
        num_to_records = len(to_link_ds.get_records())
        fields = {
            "reference_dataset": from_link_ds.id,
            "identifier": "test",
            "link": to_link_record.id,
        }
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-add", args=(from_link_ds.id,)),
            fields,
        )
        self.assertContains(response, "Reference dataset record added successfully")
        self.assertEqual(num_from_records + 1, len(from_link_ds.get_records()))
        self.assertEqual(num_to_records, len(to_link_ds.get_records()))

    def test_create_reference_dataset_circular_link(self):
        ref_ds1 = factories.ReferenceDatasetFactory.create(name="refds1", table_name="refds1")
        ref_ds2 = factories.ReferenceDatasetFactory.create(name="refds2", table_name="refds2")
        ref_ds1_field = factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )

        ref_ds2_field = factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )

        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(ref_ds2.id,)),
            {
                "id": ref_ds2.id,
                "name": ref_ds2.name,
                "table_name": ref_ds2.table_name,
                "slug": ref_ds2.slug,
                "external_database": "",
                "short_description": "xxx",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": ref_ds2_field.id,
                "fields-0-reference_dataset": ref_ds2.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
                "fields-1-reference_dataset": ref_ds2.id,
                "fields-1-name": "Added linked field",
                "fields-1-relationship_name": "linked",
                "fields-1-data_type": ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
                "fields-1-description": "Linked field",
                "fields-1-linked_reference_dataset_field": ref_ds1_field.id,
            },
        )
        self.assertTrue(ref_ds2.fields.count(), 2)
        self.assertContains(
            response,
            "A reference dataset field cannot point to another field that points back to this dataset (circular link)",
        )

    def test_reference_dataset_upload_invalid_columns(self):
        # Create ref dataset
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name="ref_invalid_upload", table_name="ref_invalid_upload"
        )
        # Create 2 ref dataset fields
        factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="name",
            column_name="name",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )

        # Create in memory file with 1 incorrect field name
        file1 = SimpleUploadedFile(
            "file1.csv",
            b"refid,invalid\r\nA1,test1\r\nA2,test2\r\n",
            content_type="text/csv",
        )

        # Assert upload fails with error message
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-upload", args=(ref_ds1.id,)),
            {"file": file1},
        )
        self.assertContains(
            response,
            "Please ensure the uploaded csv file headers include all the target reference dataset columns",
        )

    def test_reference_dataset_upload_invalid_file_type(self):
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name="ref_invalid_upload", table_name="ref_invalid_upload"
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="name",
            column_name="name",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        file1 = SimpleUploadedFile("file1.txt", b"some text\r\n", content_type="text/plain")
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-upload", args=(ref_ds1.id,)),
            {"file": file1},
        )
        self.assertContains(response, "File extension “txt” is not allowed.")

    def test_reference_data_upload(self):
        self._test_reference_data_upload(
            b"refid,name,link\r\n"  # Header
            b"B1,Updated name,\r\n"  # Update existing record
            b"B2,New record 1,A2\r\n"  # Update existing record
            b"B3,New record 2,\r\n"  # Add record without link
            b"B4,Another record,Z1\r\n"  # Invalid link
        )

    def test_reference_data_upload_with_bom(self):
        self._test_reference_data_upload(
            b"\xef\xbb\xbfrefid,name,link\r\n"  # Header
            b"B1,Updated name,\r\n"  # Update existing record
            b"B2,New record 1,A2\r\n"  # Update existing record
            b"B3,New record 2,\r\n"  # Add record without link
            b"B4,Another record,Z1\r\n"  # Invalid link
        )

    def _test_reference_data_upload(self, upload_content):
        ref_ds1 = factories.ReferenceDatasetFactory.create(
            name="ref_invalid_upload", table_name="ref_invalid_upload"
        )
        ref_ds2 = factories.ReferenceDatasetFactory.create(
            name="ref_invalid_upload2", table_name="ref_invalid_upload2"
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="name",
            column_name="name",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="refid",
            column_name="refid",
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
            is_identifier=True,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="name",
            column_name="name",
            reference_dataset=ref_ds2,
            data_type=ReferenceDatasetField.DATA_TYPE_CHAR,
        )
        factories.ReferenceDatasetFieldFactory.create(
            name="link",
            relationship_name="link",
            reference_dataset=ref_ds1,
            data_type=ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY,
            linked_reference_dataset_field=ref_ds2.fields.get(is_identifier=True),
        )
        ref_ds1.increment_schema_version()
        ref_ds2.increment_schema_version()

        # Add records to the "linked to" table
        ref_ds2.save_record(
            None, {"reference_dataset": ref_ds2, "refid": "A1", "name": "Linked to 1"}
        )
        linked_to = ref_ds2.save_record(
            None, {"reference_dataset": ref_ds2, "refid": "A2", "name": "Linked to 2"}
        )

        # Add some records to the "linked from" table
        existing_record = ref_ds1.save_record(
            None,
            {
                "reference_dataset": ref_ds1,
                "refid": "B1",
                "name": "Linked from 1",
                "link_id": linked_to.id,
            },
        )
        record_count = ref_ds1.get_records().count()
        file1 = SimpleUploadedFile("file1.csv", upload_content, content_type="text/csv")
        response = self._authenticated_post(
            reverse("dw-admin:reference-dataset-record-upload", args=(ref_ds1.id,)),
            {"file": file1},
        )
        self.assertContains(response, "Reference dataset upload completed successfully")
        self.assertContains(response, "Reference dataset upload completed successfully")
        log_records = ReferenceDatasetUploadLog.objects.last().records.all()
        self.assertEqual(log_records.count(), 4)
        self.assertEqual(
            log_records[0].status,
            ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_UPDATED,
        )
        self.assertEqual(
            log_records[1].status, ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED
        )
        self.assertEqual(
            log_records[2].status, ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED
        )
        self.assertEqual(log_records[3].status, ReferenceDatasetUploadLogRecord.STATUS_FAILURE)
        self.assertEqual(ref_ds1.get_records().count(), record_count + 2)

        # Check that the existing record was updated
        existing_record = ref_ds1.get_records().get(pk=existing_record.id)
        self.assertEqual(existing_record.name, "Updated name")
        self.assertIsNone(existing_record.link)

        # Check new record with link was created
        new_record = ref_ds1.get_record_by_custom_id("B2")
        self.assertEqual(new_record.name, "New record 1")
        self.assertIsNotNone(new_record.link)

        # Check new record without link was created
        new_record = ref_ds1.get_record_by_custom_id("B3")
        self.assertEqual(new_record.name, "New record 2")
        self.assertIsNone(new_record.link)

        # Check record with invalid link was not created
        self.assertFalse(
            ref_ds1.get_records().filter(**{ref_ds1.identifier_field.column_name: "B4"}).exists()
        )

    def test_delete_sort_field(self):
        reference_dataset = self._create_reference_dataset()
        field1 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=1, is_identifier=True
        )
        field2 = factories.ReferenceDatasetFieldFactory.create(
            reference_dataset=reference_dataset, data_type=2
        )
        reference_dataset.sort_field = field1
        reference_dataset.save()

        response = self._authenticated_post(
            reverse("admin:datasets_referencedataset_change", args=(reference_dataset.id,)),
            {
                "id": reference_dataset.id,
                "name": "test updated",
                "table_name": reference_dataset.table_name,
                "slug": "test-ref-1",
                "external_database": "",
                "short_description": "test description that is short",
                "description": "",
                "valid_from": "",
                "valid_to": "",
                "enquiries_contact": "",
                "licence": "",
                "restrictions_on_usage": "",
                "sort_field": field1.id,
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 2,
                "fields-INITIAL_FORMS": 2,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": field1.id,
                "fields-0-reference_dataset": reference_dataset.id,
                "fields-0-name": "updated_field_1",
                "fields-0-column_name": field1.column_name,
                "fields-0-data_type": 2,
                "fields-0-description": "Updated field 1",
                "fields-0-DELETE": "on",
                "fields-1-id": field2.id,
                "fields-1-reference_dataset": reference_dataset.id,
                "fields-1-name": "updated_field_2",
                "fields-1-column_name": field2.column_name,
                "fields-1-data_type": 2,
                "fields-1-description": "Updated field 2",
                "fields-1-is_identifier": "on",
                "fields-1-is_display_name": "on",
            },
        )
        self.assertContains(response, "was changed successfully")
        reference_dataset.refresh_from_db()
        self.assertIsNone(reference_dataset.sort_field)


class TestTagAdmin(BaseAdminTestCase):
    def test_tag_name_search(self):
        factories.SourceTagFactory(name="Apple")
        factories.TopicTagFactory(name="Politics")

        response = self._authenticated_get(
            reverse("admin:datasets_tag_changelist"), {"q": "apple"}
        )
        self.assertContains(response, "Source: Apple")
        self.assertNotContains(response, "Topic: Politics")

    def test_tag_type_search(self):
        factories.SourceTagFactory(name="Apple")
        factories.TopicTagFactory(name="Politics")

        response = self._authenticated_get(
            reverse("admin:datasets_tag_changelist"), {"q": "topic"}
        )
        self.assertContains(response, "Topic: Politics")
        self.assertNotContains(response, "Source: Apple")

    def test_tag_bad_search(self):
        factories.SourceTagFactory(name="Apple")
        factories.TopicTagFactory(name="Politics")

        response = self._authenticated_get(reverse("admin:datasets_tag_changelist"), {"q": "test"})
        self.assertNotContains(response, "Topic: Politics")
        self.assertNotContains(response, "Source: Apple")


class TestSourceLinkAdmin(BaseAdminTestCase):
    def test_source_link_upload_get(self):
        dataset = factories.DataSetFactory.create()
        response = self._authenticated_get(
            reverse("dw-admin:source-link-upload", args=(dataset.id,))
        )
        self.assertContains(response, "Upload source link")

    @mock.patch("dataworkspace.apps.dw_admin.views.boto3.client")
    def test_source_link_upload_failure(self, mock_client):
        mock_client().put_object.side_effect = ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="put_object",
        )
        dataset = factories.DataSetFactory.create()
        link_count = dataset.sourcelink_set.count()
        file1 = SimpleUploadedFile("file1.txt", b"This is a test", content_type="text/plain")
        response = self._authenticated_post(
            reverse("dw-admin:source-link-upload", args=(dataset.id,)),
            {
                "dataset": dataset.id,
                "name": "Test source link",
                "format": "CSV",
                "frequency": "Never",
                "file": file1,
            },
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(link_count, dataset.sourcelink_set.count())

    @mock.patch("dataworkspace.apps.dw_admin.views.boto3.client")
    def test_source_link_upload(self, mock_client):
        dataset = factories.DataSetFactory.create()
        link_count = dataset.sourcelink_set.count()
        file1 = SimpleUploadedFile("file1.txt", b"This is a test", content_type="text/plain")
        response = self._authenticated_post(
            reverse("dw-admin:source-link-upload", args=(dataset.id,)),
            {
                "dataset": dataset.id,
                "name": "Test source link",
                "format": "CSV",
                "frequency": "Never",
                "file": file1,
            },
        )
        self.assertContains(response, "Source link uploaded successfully")
        self.assertEqual(link_count + 1, dataset.sourcelink_set.count())
        link = dataset.sourcelink_set.latest("created_date")
        self.assertEqual(link.name, "Test source link")
        self.assertEqual(link.format, "CSV")
        self.assertEqual(link.frequency, "Never")
        mock_client().put_object.assert_called_once_with(
            Body=mock.ANY, Bucket=settings.AWS_UPLOADS_BUCKET, Key=link.url
        )


class TestDatasetAdmin(BaseAdminTestCase):
    def test_edit_dataset_authorized_users(self):
        dataset = factories.DataSetFactory.create()
        user1 = factories.UserFactory.create()
        user2 = factories.UserFactory.create()
        factories.DataSetUserPermissionFactory.create(dataset=dataset, user=user1)

        self.assertEqual(dataset.user_has_access(user1), True)
        self.assertEqual(dataset.user_has_access(user2), False)

        response = self._authenticated_post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": dataset.published,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": UserAccessType.REQUIRES_AUTHORIZATION,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "authorized_users": user2.id,
                "_continue": "Save and continue editing",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(dataset.user_has_access(user1), False)
        self.assertEqual(dataset.user_has_access(user2), True)

    def test_edit_dataset_authorized_email_domains(self):
        dataset = factories.DataSetFactory.create()
        user1 = factories.UserFactory.create()

        self.assertEqual(dataset.user_has_access(user1), False)

        response = self._authenticated_post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": dataset.published,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": UserAccessType.REQUIRES_AUTHORIZATION,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "authorized_email_domains": ["example.com"],
                "_continue": "Save and continue editing",
            },
        )
        dataset.refresh_from_db()
        self.assertContains(response, "was changed successfully")
        self.assertEqual(dataset.user_has_access(user1), True)

    def test_delete_external_source_link(self):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(
            link_type=SourceLink.TYPE_EXTERNAL, dataset=dataset
        )
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": dataset.published,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": UserAccessType.OPEN,
                "sourcelink_set-TOTAL_FORMS": "1",
                "sourcelink_set-INITIAL_FORMS": "1",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourcelink_set-0-id": source_link.id,
                "sourcelink_set-0-dataset": dataset.id,
                "sourcelink_set-0-name": "test",
                "sourcelink_set-0-url": "http://test.com",
                "sourcelink_set-0-format": "test",
                "sourcelink_set-0-frequency": "test",
                "sourcelink_set-0-DELETE": "on",
                "sourcelink_set-__prefix__-id": "",
                "sourcelink_set-__prefix__-dataset": "571b8aac-7dc2-4e8b-bfae-73d5c25afd04",
                "sourcelink_set-__prefix__-name": "",
                "sourcelink_set-__prefix__-url": "",
                "sourcelink_set-__prefix__-format": "",
                "sourcelink_set-__prefix__-frequency": "",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(dataset.sourcelink_set.count(), link_count - 1)

    @mock.patch("dataworkspace.apps.datasets.models.boto3.client")
    def test_delete_local_source_link_aws_failure(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(link_type=SourceLink.TYPE_LOCAL, dataset=dataset)
        link_count = dataset.sourcelink_set.count()
        mock_client.return_value.head_object.side_effect = ClientError(
            error_response={"Error": {"Message": "it failed"}},
            operation_name="head_object",
        )
        response = self._authenticated_post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": dataset.published,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": UserAccessType.OPEN,
                "sourcelink_set-TOTAL_FORMS": "1",
                "sourcelink_set-INITIAL_FORMS": "1",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourcelink_set-0-id": source_link.id,
                "sourcelink_set-0-dataset": dataset.id,
                "sourcelink_set-0-name": "test",
                "sourcelink_set-0-url": "s3://sourcelink/a-file.txt",
                "sourcelink_set-0-format": "test",
                "sourcelink_set-0-frequency": "test",
                "sourcelink_set-0-DELETE": "on",
                "sourcelink_set-__prefix__-id": "",
                "sourcelink_set-__prefix__-dataset": "571b8aac-7dc2-4e8b-bfae-73d5c25afd04",
                "sourcelink_set-__prefix__-name": "",
                "sourcelink_set-__prefix__-url": "",
                "sourcelink_set-__prefix__-format": "",
                "sourcelink_set-__prefix__-frequency": "",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dataset.sourcelink_set.count(), link_count - 1)

    @mock.patch("dataworkspace.apps.datasets.models.boto3.client")
    def test_delete_local_source_link(self, mock_client):
        dataset = factories.DataSetFactory.create()
        source_link = factories.SourceLinkFactory(link_type=SourceLink.TYPE_LOCAL, dataset=dataset)
        link_count = dataset.sourcelink_set.count()
        response = self._authenticated_post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": dataset.published,
                "name": dataset.name,
                "slug": dataset.slug,
                "user_access_type": UserAccessType.OPEN,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "sourcelink_set-TOTAL_FORMS": "1",
                "sourcelink_set-INITIAL_FORMS": "1",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourcelink_set-0-id": source_link.id,
                "sourcelink_set-0-dataset": dataset.id,
                "sourcelink_set-0-name": "test",
                "sourcelink_set-0-url": "s3://sourcelink/a-file.txt",
                "sourcelink_set-0-format": "test",
                "sourcelink_set-0-frequency": "test",
                "sourcelink_set-0-DELETE": "on",
                "sourcelink_set-__prefix__-id": "",
                "sourcelink_set-__prefix__-dataset": "571b8aac-7dc2-4e8b-bfae-73d5c25afd04",
                "sourcelink_set-__prefix__-name": "",
                "sourcelink_set-__prefix__-url": "",
                "sourcelink_set-__prefix__-format": "",
                "sourcelink_set-__prefix__-frequency": "",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
        )
        self.assertContains(response, "was changed successfully")
        self.assertEqual(dataset.sourcelink_set.count(), link_count - 1)
        mock_client().delete_object.assert_called_once_with(
            Bucket=settings.AWS_UPLOADS_BUCKET, Key="s3://sourcelink/a-file.txt"
        )


class TestDatasetAdminPytest:
    def test_sql_queries_must_be_reviewed_before_publishing(self, staff_client):
        dataset = factories.DataSetFactory.create(published=False)
        sql = factories.CustomDatasetQueryFactory.create(dataset=dataset, reviewed=False)

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "1",
                "customdatasetquery_set-INITIAL_FORMS": "1",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-0-id": sql.id,
                "customdatasetquery_set-0-dataset": str(dataset.id),
                "customdatasetquery_set-0-name": "test",
                "customdatasetquery_set-0-database": str(sql.database.id),
                "customdatasetquery_set-0-query": "select 1",
                "customdatasetquery_set-0-frequency": 1,
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert DataSet.objects.get(id=dataset.id).published is False
        assert (
            "You must review this SQL query before the dataset can be published."
            in response.content.decode(response.charset)
        )

    @pytest.mark.parametrize(
        "query, expected_tables",
        (
            ("SELECT * FROM auth_user", ["public.auth_user"]),
            ("SELECT * FROM auth_user;", ["public.auth_user"]),
            (
                "SELECT * FROM auth_user JOIN auth_user_groups ON auth_user.id = auth_user_groups.user_id",
                ["public.auth_user", "public.auth_user_groups"],
            ),
            (
                "WITH foo as (SELECT * FROM auth_user) SELECT * FROM foo",
                ["public.auth_user"],
            ),
            ("SELECT 1", []),
            ("SELECT * FROM test", []),
            ("SELECT * FROM", []),
        ),
    )
    @pytest.mark.django_db
    def test_sql_query_tables_extracted_correctly(self, staff_client, query, expected_tables):
        dataset = factories.DataSetFactory.create(published=False)
        sql = factories.CustomDatasetQueryFactory.create(dataset=dataset, reviewed=False)

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": dataset.user_access_type,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "1",
                "customdatasetquery_set-INITIAL_FORMS": "1",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-0-id": sql.id,
                "customdatasetquery_set-0-dataset": str(dataset.id),
                "customdatasetquery_set-0-name": "test",
                "customdatasetquery_set-0-database": str(sql.database.id),
                "customdatasetquery_set-0-query": query,
                "customdatasetquery_set-0-frequency": 1,
                "customdatasetquery_set-0-reviewed": True,
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == 200
        tables = CustomDatasetQuery.objects.get(id=sql.id).tables.all()
        assert sorted([f"{t.schema}.{t.table}" for t in tables]) == sorted(expected_tables)

    @pytest.mark.parametrize(
        "request_client, expected_response_code, can_review",
        (
            ("client", 404, False),
            ("sme_client", 200, False),
            ("staff_client", 200, True),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_sql_queries_can_only_be_reviewed_by_superusers(
        self, request_client, expected_response_code, can_review
    ):
        dataset = factories.DataSetFactory.create(published=False)
        sql = factories.CustomDatasetQueryFactory.create(dataset=dataset, reviewed=False)

        # Login to admin site
        request_client.post(reverse("admin:index"), follow=True)

        response = request_client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": False,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": dataset.user_access_type,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "1",
                "customdatasetquery_set-INITIAL_FORMS": "1",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-0-id": sql.id,
                "customdatasetquery_set-0-dataset": str(dataset.id),
                "customdatasetquery_set-0-name": "test",
                "customdatasetquery_set-0-database": str(sql.database.id),
                "customdatasetquery_set-0-query": "select 1",
                "customdatasetquery_set-0-frequency": 1,
                "customdatasetquery_set-0-reviewed": True,
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == expected_response_code
        assert CustomDatasetQuery.objects.get(id=sql.id).reviewed == can_review

    @pytest.mark.parametrize(
        "request_client, expected_response_code, should_publish",
        (
            ("client", 404, False),
            ("sme_client", 200, False),
            ("staff_client", 200, True),
        ),
        indirect=["request_client"],
    )
    @pytest.mark.django_db
    def test_datacut_can_only_be_published_by_superuser(
        self, request_client, expected_response_code, should_publish
    ):
        dataset = factories.DataSetFactory.create(published=False)

        # Login to admin site
        request_client.post(reverse("admin:index"), follow=True)

        response = request_client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": dataset.user_access_type,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == expected_response_code
        assert DataSet.objects.get(id=dataset.id).published == should_publish

    @pytest.mark.parametrize(
        ("manage_unpublished_permission, admin_change_view, DatasetFactory"),
        (
            (
                "manage_unpublished_master_datasets",
                "admin:datasets_masterdataset_change",
                partial(factories.DataSetFactory.create, type=DataSetType.MASTER),
            ),
            (
                "manage_unpublished_datacut_datasets",
                "admin:datasets_datacutdataset_change",
                partial(factories.DataSetFactory.create, type=DataSetType.DATACUT),
            ),
            (
                "manage_unpublished_reference_datasets",
                "admin:datasets_referencedataset_change",
                factories.ReferenceDatasetFactory.create,
            ),
        ),
    )
    @pytest.mark.django_db
    def test_manage_dataset_permission_allows_viewing_but_not_editing_published_datasets(
        self, manage_unpublished_permission, admin_change_view, DatasetFactory
    ):
        dataset = DatasetFactory(published=True)
        user = get_user_model().objects.create(is_staff=True)
        perm = Permission.objects.get(codename=manage_unpublished_permission)
        user.user_permissions.add(perm)
        user.save()

        unauthenticated_client = Client()
        authenticated_client = Client(**get_http_sso_data(user))

        for client in [unauthenticated_client, authenticated_client]:
            if client is authenticated_client:
                # Log into admin site
                client.post(reverse("admin:index"), follow=True)

            view_response = client.get(reverse(admin_change_view, args=(dataset.id,)), follow=True)
            change_response = client.post(
                reverse(admin_change_view, args=(dataset.id,)), follow=True
            )

            assert view_response.status_code == (200 if client is authenticated_client else 403)
            assert change_response.status_code == 403

    @pytest.mark.django_db
    def test_manage_master_dataset_permission_allows_editing_unpublished_datasets(self):
        dataset = factories.DataSetFactory.create(
            published=False, name="original", type=DataSetType.MASTER
        )
        user = get_user_model().objects.create(is_staff=True)
        perm = Permission.objects.get(codename="manage_unpublished_master_datasets")
        user.user_permissions.add(perm)
        user.save()

        client = Client(**get_http_sso_data(user))

        # Login to admin site
        client.post(reverse("admin:index"), follow=True)

        response = client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": False,
                "name": "changed",
                "slug": dataset.slug,
                "user_access_type": dataset.user_access_type,
                "short_description": "some description",
                "description": "some description",
                "type": 1,
                "sourcetable_set-TOTAL_FORMS": "0",
                "sourcetable_set-INITIAL_FORMS": "0",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert DataSet.objects.get(id=dataset.id).name == "changed"

    @pytest.mark.django_db
    def test_manage_datacut_dataset_permission_allows_editing_unpublished_datasets(
        self,
    ):
        dataset = factories.DataSetFactory.create(
            published=False, name="original", type=DataSetType.DATACUT
        )
        user = get_user_model().objects.create(is_staff=True)
        perm = Permission.objects.get(codename="manage_unpublished_datacut_datasets")
        user.user_permissions.add(perm)
        user.save()

        client = Client(**get_http_sso_data(user))

        # Login to admin site
        client.post(reverse("admin:index"), follow=True)

        response = client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": False,
                "name": "changed",
                "slug": dataset.slug,
                "short_description": "some description",
                "description": "some description",
                "type": 2,
                "user_access_type": dataset.user_access_type,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "0",
                "customdatasetquery_set-INITIAL_FORMS": "0",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert DataSet.objects.get(id=dataset.id).name == "changed"

    @pytest.mark.django_db
    def test_manage_reference_dataset_permission_allows_editing_unpublished_datasets(
        self,
    ):
        dataset = ReferenceDataset.objects.create(
            name="Test Reference Dataset 1",
            table_name="ref_test_dataset",
            short_description="Testing...",
            slug="test-reference-dataset-1",
            published=False,
        )
        field1 = factories.ReferenceDatasetFieldFactory(
            reference_dataset=dataset,
            data_type=1,
            is_identifier=True,
            column_name="field_1",
            description="field 1 description",
        )

        user = get_user_model().objects.create(is_staff=True)
        perm = Permission.objects.get(codename="manage_unpublished_reference_datasets")
        user.user_permissions.add(perm)
        user.save()

        client = Client(**get_http_sso_data(user))

        # Login to admin site
        client.post(reverse("admin:index"), follow=True)

        response = client.post(
            reverse("admin:datasets_referencedataset_change", args=(dataset.id,)),
            {
                "id": dataset.id,
                "name": "changed",
                "table_name": dataset.table_name,
                "slug": dataset.slug,
                "short_description": "test description that is short",
                "sort_direction": ReferenceDataset.SORT_DIR_DESC,
                "fields-TOTAL_FORMS": 1,
                "fields-INITIAL_FORMS": 1,
                "fields-MIN_NUM_FORMS": 1,
                "fields-MAX_NUM_FORMS": 1000,
                "fields-0-id": str(field1.id),
                "fields-0-reference_dataset": str(dataset.id),
                "fields-0-name": field1.name,
                "fields-0-column_name": "updated_field_1",
                "fields-0-data_type": 1,
                "fields-0-description": "updated description",
                "fields-0-is_identifier": "on",
                "fields-0-is_display_name": "on",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert ReferenceDataset.objects.get(id=dataset.id).name == "changed"

    @pytest.mark.parametrize("published, expected_reviewed_status", ((False, False), (True, True)))
    @pytest.mark.django_db
    def test_unpublished_datacut_query_review_flag_is_toggled_off_if_query_changed_when_already_reviewed(
        self, staff_client, published, expected_reviewed_status
    ):
        dataset = factories.DataSetFactory.create(published=published)
        sql = factories.CustomDatasetQueryFactory.create(
            dataset=dataset, reviewed=True, query="original query"
        )

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_datacutdataset_change", args=(dataset.id,)),
            {
                "published": published,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": 2,
                "user_access_type": dataset.user_access_type,
                "sourcelink_set-TOTAL_FORMS": "0",
                "sourcelink_set-INITIAL_FORMS": "0",
                "sourcelink_set-MIN_NUM_FORMS": "0",
                "sourcelink_set-MAX_NUM_FORMS": "1000",
                "sourceview_set-TOTAL_FORMS": "0",
                "sourceview_set-INITIAL_FORMS": "0",
                "sourceview_set-MIN_NUM_FORMS": "0",
                "sourceview_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-TOTAL_FORMS": "1",
                "customdatasetquery_set-INITIAL_FORMS": "1",
                "customdatasetquery_set-MIN_NUM_FORMS": "0",
                "customdatasetquery_set-MAX_NUM_FORMS": "1000",
                "customdatasetquery_set-0-id": sql.id,
                "customdatasetquery_set-0-dataset": str(dataset.id),
                "customdatasetquery_set-0-name": "test",
                "customdatasetquery_set-0-database": str(sql.database.id),
                "customdatasetquery_set-0-query": "select 2",
                "customdatasetquery_set-0-frequency": 1,
                "customdatasetquery_set-0-reviewed": True,
                "_continue": "Save and continue editing",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert CustomDatasetQuery.objects.get(id=sql.id).query == "select 2"
        assert CustomDatasetQuery.objects.get(id=sql.id).reviewed == expected_reviewed_status

    @mock.patch("dataworkspace.apps.datasets.admin.sync_quicksight_permissions")
    @pytest.mark.django_db
    def test_master_dataset_permission_changes_calls_sync_job(self, mock_sync, staff_client):
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.OPEN
        )

        source_table = factories.SourceTableFactory(
            name="my-source",
            table="my_table",
            dataset=dataset,
        )

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": UserAccessType.REQUIRES_AUTHORIZATION,
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "1",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-id": source_table.id,
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": source_table.name,
                "sourcetable_set-0-database": str(source_table.database.id),
                "sourcetable_set-0-schema": source_table.schema,
                "sourcetable_set-0-frequency": source_table.frequency,
                "sourcetable_set-0-table": source_table.table,
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )
        assert response.status_code == 200
        assert mock_sync.delay.call_args_list == [mock.call()]

    @mock.patch("dataworkspace.apps.datasets.admin.sync_quicksight_permissions")
    @mock.patch("dataworkspace.apps.datasets.admin.clear_schema_info_cache_for_user")
    @pytest.mark.django_db
    def test_master_dataset_authorized_user_changes_calls_sync_job_and_clears_explorer_cache(
        self, mock_clear_cache, mock_sync, staff_client
    ):
        user_1 = factories.UserFactory()
        user_2 = factories.UserFactory()

        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        source_table = factories.SourceTableFactory(
            name="my-source",
            table="my_table",
            dataset=dataset,
        )

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": dataset.user_access_type,
                "authorized_users": [str(user_1.id), str(user_2.id)],
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "1",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-id": source_table.id,
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": source_table.name,
                "sourcetable_set-0-database": str(source_table.database.id),
                "sourcetable_set-0-schema": source_table.schema,
                "sourcetable_set-0-frequency": source_table.frequency,
                "sourcetable_set-0-table": source_table.table,
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        _, mock_sync_kwargs = mock_sync.delay.call_args_list[0]
        mock_clear_cache_args = [args[0] for args, _ in mock_clear_cache.call_args_list]

        assert response.status_code == 200
        assert sorted(mock_sync_kwargs["user_sso_ids_to_update"]) == sorted(
            [str(user_1.profile.sso_id), str(user_2.profile.sso_id)]
        )
        assert sorted([u.id for u in mock_clear_cache_args]) == sorted([user_1.id, user_2.id])

    @mock.patch(
        "dataworkspace.apps.explorer.connections.connections",
        {"test_external_db": "test_external_db"},
    )
    @pytest.mark.django_db
    def test_dataset_access_type_change_invalidates_all_user_cached_credentials(
        self, staff_client
    ):
        user = factories.UserFactory()

        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        source_table = factories.SourceTableFactory(
            name="my-source",
            table="my_table",
            dataset=dataset,
        )

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        original_connection = get_user_explorer_connection_settings(user, "test_external_db")

        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": UserAccessType.REQUIRES_AUTHENTICATION,
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "1",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-id": source_table.id,
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": source_table.name,
                "sourcetable_set-0-database": str(source_table.database.id),
                "sourcetable_set-0-schema": source_table.schema,
                "sourcetable_set-0-frequency": source_table.frequency,
                "sourcetable_set-0-table": source_table.table,
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        new_connection = get_user_explorer_connection_settings(user, "test_external_db")

        assert response.status_code == 200
        assert original_connection != new_connection

    @mock.patch("dataworkspace.apps.datasets.admin.remove_data_explorer_user_cached_credentials")
    @pytest.mark.django_db
    def test_master_dataset_permission_changes_clears_authorized_users_cached_credentials(
        self, mock_remove_cached_credentials, staff_client
    ):
        user = factories.UserFactory()
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        source_table = factories.SourceTableFactory(
            name="my-source",
            table="my_table",
            dataset=dataset,
        )

        # Login to admin site
        staff_client.post(reverse("admin:index"), follow=True)

        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": UserAccessType.REQUIRES_AUTHORIZATION,
                "authorized_users": str(user.id),
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "1",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-id": source_table.id,
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": source_table.name,
                "sourcetable_set-0-database": str(source_table.database.id),
                "sourcetable_set-0-schema": source_table.schema,
                "sourcetable_set-0-frequency": source_table.frequency,
                "sourcetable_set-0-table": source_table.table,
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        assert response.status_code == 200
        # As the user has just been authorized to access the dataset, their cached
        # data explorer credentials should be cleared
        assert mock_remove_cached_credentials.call_args_list == [mock.call(user)]

    @pytest.mark.django_db
    def test_source_table_data_grid_download_enabled_without_limit(self, staff_client):
        staff_client.post(reverse("admin:index"), follow=True)
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        database = factories.DatabaseFactory()
        num_tables = SourceTable.objects.count()
        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": dataset.user_access_type,
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "0",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": "reporting table",
                "sourcetable_set-0-database": str(database.id),
                "sourcetable_set-0-schema": "test_schema",
                "sourcetable_set-0-frequency": 1,
                "sourcetable_set-0-table": "test_table",
                "sourcetable_set-0-data_grid_enabled": "on",
                "sourcetable_set-0-data_grid_download_enabled": "on",
                "sourcetable_set-0-data_grid_download_limit": "",
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert SourceTable.objects.count() == num_tables
        assert "A download limit must be set if downloads are enabled" in response.content.decode(
            "utf-8"
        )

    @pytest.mark.django_db
    def test_source_table_data_grid_enabled(self, staff_client):
        staff_client.post(reverse("admin:index"), follow=True)
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        database = factories.DatabaseFactory()
        num_tables = SourceTable.objects.count()
        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": dataset.user_access_type,
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "0",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": "reporting table",
                "sourcetable_set-0-database": str(database.id),
                "sourcetable_set-0-schema": "test_schema",
                "sourcetable_set-0-frequency": 1,
                "sourcetable_set-0-table": "test_table",
                "sourcetable_set-0-data_grid_enabled": "on",
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert SourceTable.objects.count() == num_tables + 1

    @pytest.mark.django_db
    def test_source_table_reporting_disabled(self, staff_client):
        staff_client.post(reverse("admin:index"), follow=True)
        dataset = factories.MasterDataSetFactory.create(
            published=True, user_access_type=UserAccessType.REQUIRES_AUTHORIZATION
        )
        database = factories.DatabaseFactory()
        num_tables = SourceTable.objects.count()
        response = staff_client.post(
            reverse("admin:datasets_masterdataset_change", args=(dataset.id,)),
            {
                "published": True,
                "name": dataset.name,
                "slug": dataset.slug,
                "short_description": "test short description",
                "description": "test description",
                "type": dataset.type,
                "user_access_type": dataset.user_access_type,
                "sourcetable_set-TOTAL_FORMS": "1",
                "sourcetable_set-INITIAL_FORMS": "0",
                "sourcetable_set-MIN_NUM_FORMS": "0",
                "sourcetable_set-MAX_NUM_FORMS": "1000",
                "visualisations-TOTAL_FORMS": "1",
                "visualisations-INITIAL_FORMS": "0",
                "visualisations-MIN_NUM_FORMS": "0",
                "visualisations-MAX_NUM_FORMS": "1000",
                "sourcetable_set-0-dataset": dataset.id,
                "sourcetable_set-0-name": "reporting table",
                "sourcetable_set-0-database": str(database.id),
                "sourcetable_set-0-schema": "test_schema",
                "sourcetable_set-0-frequency": 1,
                "sourcetable_set-0-table": "test_table",
                "charts-TOTAL_FORMS": "1",
                "charts-INITIAL_FORMS": "0",
                "charts-MIN_NUM_FORMS": "0",
                "charts-MAX_NUM_FORMS": "1000",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert SourceTable.objects.count() == num_tables + 1
