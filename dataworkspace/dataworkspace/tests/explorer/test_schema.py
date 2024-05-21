from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache

from dataworkspace.apps.core.models import (
    Database,
)
from dataworkspace.apps.explorer import schema
from dataworkspace.apps.datasets.constants import (
    UserAccessType,
)
from dataworkspace.tests.factories import (
    MasterDataSetFactory,
    SourceTableFactory,
)


class TestSchemaInfo:
    @pytest.fixture(scope="function", autouse=True)
    def _clear_cache(self):
        cache.clear()

    @staticmethod
    def _setup_source_dataset():
        # Sets up a source dataset with tables that already exist in the database,
        # making it convenient for testing
        database = Database.objects.get(memorable_name="my_database")
        dataset = MasterDataSetFactory(
            user_access_type=UserAccessType.REQUIRES_AUTHENTICATION,
            published=True,
        )
        SourceTableFactory(
            database=database,
            dataset=dataset,
            schema="public",
            table="auth_user",
        )
        SourceTableFactory(
            database=database,
            dataset=dataset,
            schema="public",
            table="explorer_query",
        )

    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_schema_info_returns_valid_data(self, mocked_excludes, mocked_includes, staff_user):
        self._setup_source_dataset()
        mocked_includes.return_value = None
        mocked_excludes.return_value = []
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        assert mocked_includes.called  # sanity check: ensure patch worked
        tables = [x.name.name for x in res]
        assert "explorer_query" in tables
        schemas = [x.name.schema for x in res]
        assert "public" in schemas

    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_table_exclusion_list(self, mocked_excludes, mocked_includes, staff_user):
        self._setup_source_dataset()
        mocked_includes.return_value = None
        mocked_excludes.return_value = ("explorer_",)
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" not in tables

    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_app_inclusion_list(self, mocked_excludes, mocked_includes, staff_user):
        self._setup_source_dataset()
        mocked_includes.return_value = ("auth_",)
        mocked_excludes.return_value = []
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" not in tables
        assert "auth_user" in tables

    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_app_inclusion_list_excluded(self, mocked_excludes, mocked_includes, staff_user):
        self._setup_source_dataset()
        # Inclusion list "wins"
        mocked_includes.return_value = ("explorer_",)
        mocked_excludes.return_value = ("explorer_",)
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" in tables
