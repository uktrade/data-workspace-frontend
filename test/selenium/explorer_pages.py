import os
import re

from lxml import html
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


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
        options.add_argument(
            '--disable-dev-shm-usage'
        )  # https://github.com/elgalu/docker-selenium/issues/20

        # Desktop size in order to ensure the browser has desktop styling (less than this hides certain elements
        # under test)
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)

    driver.implicitly_wait(5)
    return driver


class _BasePage:
    _url_path = ''

    def __init__(
        self,
        driver: WebDriver,
        base_url='http://dataworkspace.test:8000/data-explorer/',
    ):
        self._driver = driver
        self._page = None
        self._base_url = base_url

    @property
    def url(self) -> str:
        return self._base_url + self._url_path

    def open(self):
        self._driver.get(self.url)

    def get_html(self) -> str:
        return self._driver.page_source

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

    def click_home(self):
        link = self._driver.find_element_by_link_text('Home')
        link.click()

        home_page = HomePage(self._driver)
        assert self._driver.current_url == home_page.url

        return home_page

    def click_saved_queries(self):
        link = self._driver.find_element_by_link_text('Saved queries')
        link.click()

    def click_query_log(self):
        link = self._driver.find_element_by_link_text('Logs')
        link.click()

        query_log_page = QueryLogPage(driver=self._driver, base_url=self._base_url)
        assert self._driver.current_url == query_log_page.url

        return query_log_page


class HomePage(_BasePage):
    _url_path = '/'

    def enter_query(self, sql):
        textarea = self._driver.find_element_by_class_name('ace_text-input')
        textarea.send_keys(sql)

    def click_run(self):
        self._submit("Run")

    def click_save(self):
        self._submit("Save")

        assert "/queries/create/" in self._driver.current_url

        return CreateQueryPage(driver=self._driver, base_url=self._base_url)

    def click_format_sql(self):
        self._submit("Format SQL")

    def read_result_headers(self):
        headers = self._driver.find_elements_by_xpath(
            "//div[contains(@class, 'scrollable-table')]//th[contains(@class, 'govuk-table__header')]"
        )

        return [header.text for header in headers]

    def read_result_rows(self):
        doc = html.fromstring(self.get_html())

        results = []
        rows = doc.xpath(
            "//div[contains(@class, 'scrollable-table')]//tr[contains(@class, 'govuk-table__row')]"
        )

        for row in rows[1:]:  # Drop the header row out
            results.append(
                [
                    cell.text.strip()
                    for cell in row.xpath(
                        ".//td[contains(@class, 'govuk-table__cell')]"
                    )
                ]
            )

        return results

    def read_sql(self):
        textarea = self._driver.find_element_by_id('original-sql')
        return textarea.get_attribute('value')

    def change_results_pagination(self, page, results_per_page):
        query_page = self._driver.find_element_by_id('query-page')
        query_page.clear()
        query_page.send_keys(str(page))

        query_rows = self._driver.find_element_by_id('query-rows')
        query_rows.clear()
        query_rows.send_keys(str(results_per_page))

        fetch_page = self._driver.find_element_by_xpath(
            "//button[normalize-space(text()) = 'Fetch page']"
        )
        fetch_page.click()

    def click_full_width(self):
        toggle = self._driver.find_element_by_id('full-width')
        toggle.click()

    def click_normal_width(self):
        toggle = self._driver.find_element_by_id('normal-width')
        toggle.click()


class CreateQueryPage(_BasePage):
    _url_path = '/queries/create'

    def set_title(self, title):
        field = self._driver.find_element_by_name('title')
        field.send_keys(title)

    def set_description(self, description):
        field = self._driver.find_element_by_name('description')
        field.send_keys(description)

    def click_save(self):
        self._submit("Save")

        matches_expected_url = re.search(r'/queries/(\d+)/', self._driver.current_url)
        assert matches_expected_url

        return QueryDetailPage(
            driver=self._driver,
            base_url=self._base_url,
            query_id=matches_expected_url.group(1),
        )


class QueryDetailPage(_BasePage):
    _url_path = '/queries/{query_id}'

    def __init__(self, query_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.query_id = query_id
        self._url_path = QueryDetailPage._url_path.format(query_id=self.query_id)

    def read_title(self):
        return self._get_input_field('Title').get_attribute('value')

    def read_description(self):
        return self._get_input_field('Description').get_attribute('value')

    def read_sql(self):
        return self._get_input_field('SQL').get_attribute('value')

    def click_edit(self):
        self._submit("Edit SQL")

        home_page = HomePage(driver=self._driver, base_url=self._base_url)

        return home_page


class QueryLogPage(_BasePage):
    _url_path = '/logs/'
