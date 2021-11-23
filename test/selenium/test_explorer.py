from time import sleep
from uuid import uuid4

import pytest
import requests
from django.core.cache import cache

from dataworkspace.apps.datasets.constants import UserAccessType
from test.selenium.common import get_driver  # pylint: disable=wrong-import-order
from test.selenium.conftest import (  # pylint: disable=wrong-import-order
    create_sso,
    create_dataset,
    set_dataset_access_type,
    reset_data_explorer_credentials,
)
from test.selenium.explorer_pages import HomePage  # pylint: disable=wrong-import-order


class TestDataExplorer:
    driver = None
    sso = None

    @pytest.fixture(scope="function")
    def _application(self, create_application):
        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "explorer@test.com",
                "contact_email": "explorer@test.com",
                "related_emails": [],
                "first_name": "Eddie",
                "last_name": "Eagle",
                "user_id": "9931f73c-469d-4110-9f58-92a74ab1bbfa",
            }
        }
        with create_sso(is_logged_in, codes, tokens, auth_to_me) as sso:
            tries = 240  # 60 seconds
            while tries >= 0:
                try:
                    resp = requests.get("http://dataworkspace.test:8000/healthcheck")
                except Exception:  # pylint: disable=broad-except
                    pass
                else:
                    if resp.status_code == 200:
                        break
                tries -= 1
                sleep(0.25)

            TestDataExplorer.driver = get_driver()
            TestDataExplorer.sso = sso

            cache.clear()

            yield

    def test_can_execute_query(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        home_page.click_run()
        home_page.wait_for_results()

        assert home_page.read_result_headers() == ["?column?", "?column?", "?column?"]
        assert home_page.read_result_rows() == [["1", "2", "3"]]

    def test_query_exception_returned_as_friendly_error(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query('select "invalid identifier"')
        home_page.click_run()

        sql_error_lines = home_page.read_sql_error()

        assert (
            sql_error_lines
            == 'column "invalid identifier" does not exist LINE 3: select "invalid identifier" ^'
        )

    def test_results_pagination(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select unnest(array[1, 2, 3]) as numbers")
        home_page.click_run()

        home_page.change_results_pagination(page=1, results_per_page=2)

        assert home_page.read_result_headers() == ["numbers"]
        assert home_page.read_result_rows() == [["1"], ["2"]]

        home_page.change_results_pagination(page=2, results_per_page=2)

        assert home_page.read_result_headers() == ["numbers"]
        assert home_page.read_result_rows() == [["3"]]

    def test_format_sql(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select unnest(array[1, 2, 3]) as numbers")
        home_page.click_format_sql()

        assert home_page.read_sql() == "select\n  unnest(array [1, 2, 3]) as numbers"

    def test_save_and_run_a_query(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        save_page = home_page.click_save()

        title = uuid4()
        save_page.set_title(str(title))
        save_page.set_description("I am a lovely query")

        query_detail_page = save_page.click_save()

        assert query_detail_page.read_title() == str(title)
        assert query_detail_page.read_description() == "I am a lovely query"
        assert query_detail_page.read_sql() == "select 1, 2, 3"

        edit_query_on_home_page = query_detail_page.click_edit()
        edit_query_on_home_page.click_run()

        assert edit_query_on_home_page.read_result_headers() == [
            "?column?",
            "?column?",
            "?column?",
        ]
        assert edit_query_on_home_page.read_result_rows() == [["1", "2", "3"]]

        query_log_page = edit_query_on_home_page.click_query_log()
        assert str(title) in query_log_page.get_html()
        assert "select 1, 2, 3" in query_log_page.get_html()

    def test_query_execution_logs(self, _application):
        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        save_page = home_page.click_save()

        title = uuid4()
        save_page.set_title(str(title))
        save_page.set_description("I am a lovely query")

        query_detail_page = save_page.click_save()

        assert query_detail_page.read_title() == str(title)
        assert query_detail_page.read_description() == "I am a lovely query"
        assert query_detail_page.read_sql() == "select 1, 2, 3"

        edit_query_on_home_page = query_detail_page.click_edit()
        edit_query_on_home_page.click_run()

        assert edit_query_on_home_page.read_result_headers() == [
            "?column?",
            "?column?",
            "?column?",
        ]
        assert edit_query_on_home_page.read_result_rows() == [["1", "2", "3"]]

        query_log_page = edit_query_on_home_page.click_query_log()
        assert str(title) in query_log_page.get_html()
        assert "select 1, 2, 3" in query_log_page.get_html()

    def test_user_can_only_read_from_datasets_they_have_access_to(self, _application):
        dataset_1_id = "47146cc4-1668-4522-82b6-eb5e5de7b044"
        table_1_id = "164acfc5-3852-400e-a99d-2c7c4eff8555"
        dataset_2_id = "73534d36-72f7-41b7-ad92-4d277980229e"
        table_2_id = "0a5a7f68-9e38-422d-94d6-92a366da1ab5"
        create_dataset(
            dataset_1_id,
            "explorer_dataset",
            table_1_id,
            "my_database",
            UserAccessType.REQUIRES_AUTHENTICATION,
        )
        create_dataset(
            dataset_2_id,
            "explorer_dataset_2",
            table_2_id,
            "my_database",
            UserAccessType.REQUIRES_AUTHORIZATION,
        )

        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select count(*) as count from public.explorer_dataset")
        home_page.click_run()

        assert home_page.read_result_headers() == ["count"]
        assert home_page.read_result_rows() == [["0"]]
        assert "permission denied for relation" not in home_page.get_html()

        home_page.open()  # Reset the page, i.e. to remove the existing query
        home_page.enter_query("select count(*) as count from public.explorer_dataset_2")
        home_page.click_run()

        assert home_page.read_result_headers() == []
        assert home_page.read_result_rows() == []
        assert "permission denied for relation" in home_page.get_html()

    def test_data_explorer_cached_credentials_can_be_reset_using_admin_action(self, _application):
        # This doesn't strictly test that the action is available to an admin, but it does test the routine
        # that the admin action uses.

        dataset_1_id = "47146cc4-1668-4522-82b6-eb5e5de7b044"
        table_1_id = "164acfc5-3852-400e-a99d-2c7c4eff8555"
        dataset_2_id = "73534d36-72f7-41b7-ad92-4d277980229e"
        table_2_id = "0a5a7f68-9e38-422d-94d6-92a366da1ab5"
        create_dataset(
            dataset_1_id,
            "explorer_dataset",
            table_1_id,
            "my_database",
            UserAccessType.REQUIRES_AUTHENTICATION,
        )
        create_dataset(
            dataset_2_id,
            "explorer_2_dataset",
            table_2_id,
            "my_database",
            UserAccessType.REQUIRES_AUTHENTICATION,
        )

        home_page = HomePage(driver=self.driver)
        home_page.open()

        home_page.enter_query("select count(*) as count from public.explorer_dataset")
        home_page.click_run()

        assert home_page.read_result_headers() == ["count"]
        assert home_page.read_result_rows() == [["0"]]
        assert "permission denied for relation" not in home_page.get_html()
        assert "Columns in public.explorer_dataset" in home_page.get_html()
        assert "Columns in public.explorer_2_dataset" in home_page.get_html()

        set_dataset_access_type(dataset_1_id, UserAccessType.REQUIRES_AUTHORIZATION)

        home_page.open()  # Reset the page, i.e. to remove the existing query
        home_page.enter_query("select count(*) as count from public.explorer_dataset")
        home_page.click_run()

        # Should still be using cached credentials, so still available. (Note: this isn't ideal, but _is_ how things
        # should be working based on the current implementation.
        assert home_page.read_result_headers() == ["count"]
        assert home_page.read_result_rows() == [["0"]]
        assert "permission denied for relation" not in home_page.get_html()
        assert "Columns in public.explorer_dataset" in home_page.get_html()
        assert "Columns in public.explorer_2_dataset" in home_page.get_html()

        reset_data_explorer_credentials(user_sso_id="9931f73c-469d-4110-9f58-92a74ab1bbfa")

        home_page.open()  # Reset the page, i.e. to remove the existing query
        home_page.enter_query("select count(*) as count from public.explorer_dataset")
        home_page.click_run()

        # The cached credentials should have been cleared, so new ones will be generated where access isn't available.
        assert home_page.read_result_headers() == []
        assert home_page.read_result_rows() == []
        assert "permission denied for relation" in home_page.get_html()
        assert "Columns in public.explorer_dataset" not in home_page.get_html()
        assert "Columns in public.explorer_2_dataset" in home_page.get_html()
