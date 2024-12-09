from typing import Type

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
    _url_regex = r"/support-and-feedback"

    def select_new_dataset_option(self) -> "RequestDataPage":
        self.select_radio_button("id_support_type_1")
        self._submit("Continue")

        return self._check_url_and_return_page(RequestDataPage)


class ContactUsPage(_BaseWorkspacePage):
    _url_path = "/contact-us/"
    _url_regex = r"/contact-us"

    def select_get_help_option(self) -> "SupportPage":
        self.select_radio_button("id_contact_type_0")
        self._submit("Continue")

        return self._check_url_and_return_page(SupportPage)


class RequestDataPage(_BaseWorkspacePage):
    _url_regex = r"/support/add-dataset-request/\?email=request-data@test.com"
    _url_path = "/support/add-dataset-request/?email=request-data@test.com"

    def enter_description(self, text):
        textarea = self._get_input_field("Tell us about the data you want to add")
        textarea.send_keys(text)

    def click_submit(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        self._submit("Submit")
        return self._check_url_and_return_page(new_page_class)


class RequestDataConfirmationPage(_BaseWorkspacePage):
    _url_regex = r"/support/success/(.*)\?add_dataset=True"
    _url_path = "/support/success/1234567890987654321?add_dataset=True"
