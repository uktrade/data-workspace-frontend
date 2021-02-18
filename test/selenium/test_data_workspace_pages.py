from time import sleep

import pytest
import requests
from django.core.cache import cache

from test.selenium.common import get_driver  # pylint: disable=wrong-import-order
from test.selenium.conftest import (  # pylint: disable=wrong-import-order
    create_sso,
    create_dataset,
    make_superuser,
)
from test.selenium.data_workspace_pages import (  # pylint: disable=wrong-import-order
    MasterDatasetCataloguePage,
)


class TestDataWorkspace:
    driver = None
    sso = None

    @pytest.fixture(scope='function')
    def _application(self, create_application):
        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'workspace@test.com',
                'contact_email': 'workspace@test.com',
                'related_emails': [],
                'first_name': 'Tommy',
                'last_name': 'Smith',
                'user_id': '9931f73c-469d-4110-9f58-92a74ab1bbfb',
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

            TestDataWorkspace.driver = get_driver()
            TestDataWorkspace.sso = sso

            cache.clear()

            yield

    def test_master_catalogue_page_shows_copy_code_button(self, _application):
        """Copy code button uses JS to be setup, so need to test it via selenium

        This doesn't test that the button *actually* copies the code to the clipboard - but it does at least
        make sure they exist..."""
        dataset_1_id = '47146cc4-1668-4522-82b6-eb5e5de7b044'
        table_1_id = '164acfc5-3852-400e-a99d-2c7c4eff8555'
        create_dataset(
            dataset_1_id,
            'test_dataset',
            table_1_id,
            'my_database',
            'REQUIRES_AUTHENTICATION',
        )
        make_superuser("workspace@test.com")

        master_dataset_page = MasterDatasetCataloguePage(
            driver=self.driver, url_data=dict(dataset_id=dataset_1_id)
        )
        master_dataset_page.open()

        master_dataset_page.click_code_snippets_and_columns_toggle('test_dataset')

        master_dataset_page.click_copy_code('test_dataset', 'SQL')
        master_dataset_page.click_copy_code('test_dataset', 'Python')
        master_dataset_page.click_copy_code('test_dataset', 'R')
