from typing import Type

from dataworkspace.apps.request_data.models import RoleType, SecurityClassificationType
from test.selenium.common import (  # pylint: disable=wrong-import-order
    _BasePage,
    _PageClassType,
)


class _BaseWorkspacePage(_BasePage):
    def click_header_link(self, label, new_page_class: Type[_PageClassType]) -> _PageClassType:
        link = self._driver.find_element(
            "xpath",
            f'//a[contains(@class, "govuk-header__link") and normalize-space(text()) = "{label}"]',
        )
        link.click()

        return self._check_url_and_return_page(new_page_class)


class HomePage(_BaseWorkspacePage):
    pass


class SupportPage(_BaseWorkspacePage):
    _url_path = "/support-and-feedback/"

    def select_new_dataset_option(self) -> "RequestDataPage":
        self.select_radio_button("id_support_type_1")
        self._submit("Continue")

        return self._check_url_and_return_page(RequestDataPage)


class ContactUsPage(_BaseWorkspacePage):
    _url_path = "/contact-us/"

    def select_get_help_option(self) -> "SupportPage":
        self.select_radio_button("id_contact_type_0")
        self._submit("Continue")

        return self._check_url_and_return_page(SupportPage)


class RequestDataPage(_BaseWorkspacePage):
    _url_path = "/request-data/"

    def click_start(self) -> "RequestDataWhoAreYouPage":
        self._submit("Start now")

        return self._check_url_and_return_page(RequestDataWhoAreYouPage)


class RequestDataWhoAreYouPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/who-are-you"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/who-are-you"

    def select_role(self, role_type: RoleType):
        element = self._get_input_field(role_type.label)
        element.click()

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataOwnerOrManagerPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/owner-or-manager"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/owner-or-manager"

    def enter_name(self, text):
        textarea = self._get_input_field("Name of information asset owner or manager")
        textarea.send_keys(text)

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataDescriptionPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/description"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/description"

    def enter_description(self, text):
        textarea = self._get_input_field("Describe the data you want to add")
        textarea.send_keys(text)

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataPurposePage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/purpose"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/purpose"

    def enter_purpose(self, text):
        textarea = self._get_input_field("What will the data be used for?")
        textarea.send_keys(text)

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataSecurityClassificationPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/security-classification"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/security-classification"

    def select_security_classification(self, security_classification: SecurityClassificationType):
        element = self._get_input_field(security_classification.label)
        element.click()

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataLocationPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/location"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/location"

    def enter_location(self, text):
        textarea = self._get_input_field("Where is the data currently held?")
        textarea.send_keys(text)

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataLicencePage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/licence"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/licence"

    def enter_location(self, text):
        textarea = self._get_input_field("How is the data licensed?")
        textarea.send_keys(text)

    def click_continue(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Continue")
        return self._check_url_and_return_page(new_page_class)


class RequestDataCheckAnswersPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/check-answers"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/check-answers"

    def enter_location(self, text):
        textarea = self._get_input_field("Where is the data currently held?")
        textarea.send_keys(text)

    def click_accept(self):
        self._submit("Accept and send")
        return self._check_url_and_return_page(RequestDataConfirmationPage)


class RequestDataConfirmationPage(_BaseWorkspacePage):
    _url_regex = r"/request-data/(?P<pk>\d+)/confirmation"

    @property
    def _url_path(self):
        return f"/request-data/{self._url_data['pk']}/confirmation"
