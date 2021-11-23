from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache

from dataworkspace.apps.explorer import schema


class TestSchemaInfo:
    @pytest.fixture(scope="function", autouse=True)
    def _clear_cache(self):
        cache.clear()

    @staticmethod
    def _get_connection_data():
        connection_info = settings.DATABASES_DATA["my_database"]

        return {
            "db_host": connection_info["HOST"],
            "db_port": connection_info["PORT"],
            "db_user": connection_info["USER"],
            "db_password": connection_info["PASSWORD"],
            "db_name": connection_info["NAME"],
        }

    @patch("dataworkspace.apps.explorer.schema.get_user_explorer_connection_settings")
    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_schema_info_returns_valid_data(
        self, mocked_excludes, mocked_includes, mock_connection_settings, staff_user
    ):
        mocked_includes.return_value = None
        mocked_excludes.return_value = []
        mock_connection_settings.return_value = self._get_connection_data()
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        assert mocked_includes.called  # sanity check: ensure patch worked
        tables = [x.name.name for x in res]
        assert "explorer_query" in tables
        schemas = [x.name.schema for x in res]
        assert "public" in schemas

    @patch("dataworkspace.apps.explorer.schema.get_user_explorer_connection_settings")
    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_table_exclusion_list(
        self, mocked_excludes, mocked_includes, mock_connection_settings, staff_user
    ):
        mocked_includes.return_value = None
        mocked_excludes.return_value = ("explorer_",)
        mock_connection_settings.return_value = self._get_connection_data()
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" not in tables

    @patch("dataworkspace.apps.explorer.schema.get_user_explorer_connection_settings")
    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_app_inclusion_list(
        self, mocked_excludes, mocked_includes, mock_connection_settings, staff_user
    ):
        mocked_includes.return_value = ("auth_",)
        mocked_excludes.return_value = []
        mock_connection_settings.return_value = self._get_connection_data()
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" not in tables
        assert "auth_user" in tables

    @patch("dataworkspace.apps.explorer.schema.get_user_explorer_connection_settings")
    @patch("dataworkspace.apps.explorer.schema._get_includes")
    @patch("dataworkspace.apps.explorer.schema._get_excludes")
    def test_app_inclusion_list_excluded(
        self, mocked_excludes, mocked_includes, mock_connection_settings, staff_user
    ):
        # Inclusion list "wins"
        mocked_includes.return_value = ("explorer_",)
        mocked_excludes.return_value = ("explorer_",)
        mock_connection_settings.return_value = self._get_connection_data()
        res = schema.schema_info(staff_user, settings.EXPLORER_CONNECTIONS["Postgres"])
        tables = [x.name.name for x in res]
        assert "explorer_query" in tables
