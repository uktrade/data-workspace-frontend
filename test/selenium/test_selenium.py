from time import sleep
from uuid import uuid4

import pytest
import requests

from test.selenium.conftest import create_sso  # pylint: disable=wrong-import-order
from test.selenium.explorer_pages import (  # pylint: disable=wrong-import-order
    HomePage,
    get_driver,
)


class TestDataExplorer:
    driver = None
    sso = None

    @pytest.fixture(scope='function')
    def _application(self, create_application):
        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'test@test.com',
                'contact_email': 'test@test.com',
                'related_emails': [],
                'first_name': 'Peter',
                'last_name': 'Piper',
                'user_id': '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
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

            yield

    def test_can_execute_query(self, _application):
        home_page = HomePage(
            driver=self.driver, base_url="http://dataworkspace.test:8000/data-explorer"
        )
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        home_page.click_run()

        assert home_page.read_result_headers() == ['?column?', '?column?', '?column?']
        assert home_page.read_result_rows() == [["1", "2", "3"]]

    def test_results_pagination(self, _application):
        home_page = HomePage(
            driver=self.driver, base_url="http://dataworkspace.test:8000/data-explorer"
        )
        home_page.open()

        home_page.enter_query("select unnest(array[1, 2, 3]) as numbers")
        home_page.click_run()

        home_page.change_results_pagination(page=1, results_per_page=2)

        assert home_page.read_result_headers() == ['numbers']
        assert home_page.read_result_rows() == [["1"], ["2"]]

        home_page.change_results_pagination(page=2, results_per_page=2)

        assert home_page.read_result_headers() == ['numbers']
        assert home_page.read_result_rows() == [["3"]]

    def test_format_sql(self, _application):
        home_page = HomePage(
            driver=self.driver, base_url="http://dataworkspace.test:8000/data-explorer"
        )
        home_page.open()

        home_page.enter_query("select unnest(array[1, 2, 3]) as numbers")
        home_page.click_format_sql()

        assert home_page.read_sql() == "select\n  unnest(array [1, 2, 3]) as numbers"

    def test_save_and_run_a_query(self, _application):
        home_page = HomePage(
            driver=self.driver, base_url="http://dataworkspace.test:8000/data-explorer"
        )
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        save_page = home_page.click_save()

        title = uuid4()
        save_page.set_title(str(title))
        save_page.set_description("I am a lovely query")

        query_detail_page = save_page.click_save()

        assert query_detail_page.read_title() == str(title)
        assert query_detail_page.read_description() == 'I am a lovely query'
        assert query_detail_page.read_sql() == 'select 1, 2, 3'

        edit_query_on_home_page = query_detail_page.click_edit()
        edit_query_on_home_page.click_run()

        assert edit_query_on_home_page.read_result_headers() == [
            '?column?',
            '?column?',
            '?column?',
        ]
        assert edit_query_on_home_page.read_result_rows() == [["1", "2", "3"]]

        query_log_page = edit_query_on_home_page.click_query_log()
        assert f"Query {query_detail_page.query_id}" in query_log_page.get_html()
        assert "select 1, 2, 3" in query_log_page.get_html()

    def test_query_execution_logs(self, _application):
        home_page = HomePage(
            driver=self.driver, base_url="http://dataworkspace.test:8000/data-explorer"
        )
        home_page.open()

        home_page.enter_query("select 1, 2, 3")
        save_page = home_page.click_save()

        title = uuid4()
        save_page.set_title(str(title))
        save_page.set_description("I am a lovely query")

        query_detail_page = save_page.click_save()

        assert query_detail_page.read_title() == str(title)
        assert query_detail_page.read_description() == 'I am a lovely query'
        assert query_detail_page.read_sql() == 'select 1, 2, 3'

        edit_query_on_home_page = query_detail_page.click_edit()
        edit_query_on_home_page.click_run()

        assert edit_query_on_home_page.read_result_headers() == [
            '?column?',
            '?column?',
            '?column?',
        ]
        assert edit_query_on_home_page.read_result_rows() == [["1", "2", "3"]]

        query_log_page = edit_query_on_home_page.click_query_log()
        assert f"Query {query_detail_page.query_id}" in query_log_page.get_html()
        assert "select 1, 2, 3" in query_log_page.get_html()
