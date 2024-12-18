import time

import pytest
import requests

from django.core.cache import cache

from test.selenium.common import get_driver  # pylint: disable=wrong-import-order
from test.selenium.conftest import (  # pylint: disable=wrong-import-order
    create_sso,
    create_zendesk,
)
from test.selenium.workspace_pages import (  # pylint: disable=wrong-import-order
    ContactUsPage,
    HomePage,
    RequestDataConfirmationPage,
)


class TestRequestData:
    driver = None
    sso = None

    @pytest.fixture(scope="function")
    def _application(self, create_application):
        is_logged_in = True
        codes = iter(["some-code"])
        tokens = iter(["token-1"])
        auth_to_me = {
            "Bearer token-1": {
                "email": "request-data@test.com",
                "contact_email": "request-data@test.com",
                "related_emails": [],
                "first_name": "Iwantsome",
                "last_name": "Lovelydata",
                "user_id": "9931f73c-469d-4110-9f58-92a74ab1bbfa",
            }
        }
        with create_sso(
            is_logged_in, codes, tokens, auth_to_me
        ) as sso, create_zendesk() as zendesk:
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
                time.sleep(0.25)

            self.__class__.driver = get_driver()
            self.__class__.sso = sso
            self.__class__.zendesk = zendesk

            cache.clear()

            yield

    def test_happy_path(self, _application):
        home_page = HomePage(self.driver)
        home_page.open()

        # Get to the "Request data" starting page
        contact_us_page = home_page.click_header_link("Contact us", ContactUsPage)

        support_page = contact_us_page.select_get_help_option()
        request_data_page = support_page.select_new_dataset_option()

        # fill in form with message
        message = "the data is such and such"
        request_data_page.enter_description(message)

        # Confirm that the answers are correct
        confirmation_page = request_data_page.click_submit(RequestDataConfirmationPage)
        assert "1234567890987654321" in confirmation_page.get_html()

        # Check that the request data has been posted to Zendesk
        submitted_tickets = requests.get(
            "http://dataworkspace.test:8006/_meta/read-submitted-tickets"
        ).json()

        assert len(submitted_tickets) == 1
        ticket_data = submitted_tickets[0]["ticket"]
        assert message in ticket_data["description"]
