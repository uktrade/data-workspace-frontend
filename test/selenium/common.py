import os
import re
from typing import Optional, Dict, TypeVar, Type
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.remote.webdriver import WebDriver


_PageClassType = TypeVar('_PageClassType')


def get_driver():
    if os.environ.get("REMOTE_SELENIUM_URL"):
        options = webdriver.ChromeOptions()
        driver = webdriver.Remote(
            command_executor=os.environ['REMOTE_SELENIUM_URL'],
            desired_capabilities=DesiredCapabilities.CHROME,
            options=options,
        )
    else:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')

        # Desktop size in order to ensure the browser has desktop styling (less than this hides certain elements
        # under test)
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)

    driver.implicitly_wait(5)
    return driver


class _BasePage:
    _url_regex = None
    _url_path = ''

    def __init__(
        self,
        driver: WebDriver,
        base_url='http://dataworkspace.test:8000',
        url_data: Optional[Dict] = None,
    ):
        self._driver = driver
        self._page = None
        self._base_url = base_url
        self._url_data = url_data

    @classmethod
    def parse_url(cls, url):
        if cls._url_regex is None:
            raise Exception(
                f"{cls.__class__} has no `_url_regex` definition required to parse the URL"
            )

        matches = re.match(cls._url_regex, url)
        return matches.groupdict()

    @property
    def url(self) -> str:
        return self._base_url + self._url_path

    def open(self):
        self._driver.get(self.url)

    def get_html(self) -> str:
        return self._driver.page_source

    def _check_url_and_return_page(self, new_page_class: Type[_PageClassType]) -> _PageClassType:
        if new_page_class._url_regex:
            parsed_url = urlparse(self._driver.current_url)
            current_path = parsed_url.path + ('?' + parsed_url.query if parsed_url.query else '')
            url_data = new_page_class.parse_url(current_path)
            new_page = new_page_class(self._driver, url_data=url_data)

        else:
            new_page = new_page_class(self._driver)

        assert self._driver.current_url == new_page.url
        return new_page

    def _submit(self, label):
        button = self._driver.find_element_by_xpath(
            f"//button[normalize-space(text()) = '{label}']"
        )
        button.click()

    def _get_input_field(self, field_label):
        return self._driver.find_element_by_xpath(
            f"//*[@id = //label[normalize-space(text()) = '{field_label}']/@for]"
        )

    def _fill_field(self, field_label, text):
        field = self._get_input_field(field_label)
        field.send_keys(text)

    def click_link(self, link_text, new_page_class: Optional[Type[_PageClassType]]):
        link = self._driver.find_element_by_link_text(link_text)
        link.click()

        if new_page_class:
            return self._check_url_and_return_page(new_page_class)

        return None

    def select_radio_button(self, button_id):
        self._driver.find_element_by_id(button_id).click()
