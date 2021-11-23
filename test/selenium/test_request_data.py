import time

import pytest
import requests

from django.core.cache import cache

from dataworkspace.apps.request_data.models import RoleType, SecurityClassificationType
from test.selenium.common import get_driver  # pylint: disable=wrong-import-order
from test.selenium.conftest import (  # pylint: disable=wrong-import-order
    create_sso,
    create_zendesk,
)
from test.selenium.workspace_pages import (  # pylint: disable=wrong-import-order
    HomePage,
    RequestDataOwnerOrManagerPage,
    RequestDataDescriptionPage,
    RequestDataPurposePage,
    RequestDataSecurityClassificationPage,
    RequestDataLocationPage,
    RequestDataCheckAnswersPage,
    SupportPage,
    RequestDataLicencePage,
)


class TestRequestData:
    driver = None
    sso = None

    @pytest.fixture(scope='function')
    def _application(self, create_application):
        is_logged_in = True
        codes = iter(['some-code'])
        tokens = iter(['token-1'])
        auth_to_me = {
            'Bearer token-1': {
                'email': 'request-data@test.com',
                'contact_email': 'request-data@test.com',
                'related_emails': [],
                'first_name': 'Iwantsome',
                'last_name': 'Lovelydata',
                'user_id': '9931f73c-469d-4110-9f58-92a74ab1bbfa',
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
        support_page = home_page.click_header_link('Support', SupportPage)
        request_data_page = support_page.select_new_dataset_option()

        who_are_you_page = request_data_page.click_start()

        # Answer the "who are you" question - we aren't IAM/IAO so will need to say who one of them is in next
        # question.
        who_are_you_page.select_role(RoleType.other)
        owner_or_manager_page = who_are_you_page.click_continue(RequestDataOwnerOrManagerPage)

        # Answer the "name of IAM/IAO" question
        owner_or_manager_page.enter_name("Bobby Tables")
        description_page = owner_or_manager_page.click_continue(RequestDataDescriptionPage)

        # Answer the "describe the data" question
        description_page.enter_description("It’s data about DIT")
        purpose_page = description_page.click_continue(RequestDataPurposePage)

        # Answer the "purpose of data" question
        purpose_page.enter_purpose(
            "Do you want to build a dashbooaardd? Yes I want to build a dashboard!"
        )
        security_classification_page = purpose_page.click_continue(
            RequestDataSecurityClassificationPage
        )

        # Answer the "security classification" question
        security_classification_page.select_security_classification(
            SecurityClassificationType.personal
        )
        location_page = security_classification_page.click_continue(RequestDataLocationPage)

        # Answer the "location of data" question
        location_page.enter_location("It’s in this very easy to access API")
        licence_page = location_page.click_continue(RequestDataLicencePage)

        # Answer the "licence of data" question
        licence_page.enter_location("Completely public, open data with no licence")
        check_answers_page = licence_page.click_continue(RequestDataCheckAnswersPage)

        # Confirm that the answers are correct
        confirmation_page = check_answers_page.click_accept()
        assert "1234567890987654321" in confirmation_page.get_html()

        # Check that the request data has been posted to Zendesk
        submitted_tickets = requests.get(
            'http://dataworkspace.test:8006/_meta/read-submitted-tickets'
        ).json()

        assert len(submitted_tickets) == 1
        ticket_data = submitted_tickets[0]['ticket']
        assert "Bobby Tables" in ticket_data['description']
        assert "It’s data about DIT" in ticket_data['description']
        assert (
            "Do you want to build a dashbooaardd? Yes I want to build a dashboard!"
            in ticket_data['description']
        )
        assert "It’s in this very easy to access API" in ticket_data['description']
        assert "Completely public, open data with no licence" in ticket_data['description']
        assert "request-data@test.com" in ticket_data['description']
        assert "Iwantsome Lovelydata" in ticket_data['description']
