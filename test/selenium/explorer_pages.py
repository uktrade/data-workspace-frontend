from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from test.selenium.common import _BasePage  # pylint: disable=wrong-import-order


class _BaseExplorerPage(_BasePage):
    def click_home(self):
        link = self._driver.find_element_by_link_text("Home")
        link.click()

        self._check_url_and_return_page(HomePage)

    def click_saved_queries(self):
        link = self._driver.find_element_by_link_text("Saved queries")
        link.click()

    def click_query_log(self):
        link = self._driver.find_element_by_link_text("Logs")
        link.click()

        return self._check_url_and_return_page(QueryLogPage)


class HomePage(_BaseExplorerPage):
    _url_path = "/data-explorer/"

    def enter_query(self, sql):
        textarea = self._driver.find_element_by_class_name("ace_text-input")
        textarea.send_keys(sql)

    def click_run(self):
        self._submit("Run")

    def click_save(self):
        self._submit("Save")
        return self._check_url_and_return_page(CreateQueryPage)

    def click_format_sql(self):
        self._submit("Format SQL")

    def click_cancel(self):
        self._submit("Cancel")

    def wait_for_results(self):
        WebDriverWait(self._driver, 10).until(
            expected_conditions.visibility_of_element_located((By.ID, "query-results"))
        )

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
                    for cell in row.xpath(".//td[contains(@class, 'govuk-table__cell')]//pre")
                ]
            )

        return results

    def read_sql(self):
        textarea = self._driver.find_element_by_id("original-sql")
        return textarea.get_attribute("value")

    def read_sql_error(self):
        span = self._driver.find_element_by_id("sql-error")
        return span.text

    def change_results_pagination(self, page, results_per_page):
        query_page = self._driver.find_element_by_id("query-page")
        query_page.clear()
        query_page.send_keys(str(page))

        query_rows = self._driver.find_element_by_id("query-rows")
        query_rows.clear()
        query_rows.send_keys(str(results_per_page))

        fetch_page = self._driver.find_element_by_xpath(
            "//button[normalize-space(text()) = 'Fetch page']"
        )
        fetch_page.click()


class CreateQueryPage(_BaseExplorerPage):
    _url_regex = r"/data-explorer/queries/create/\?play_id=(?P<play_id>\d+)"

    @property
    def _url_path(self):
        return f'/data-explorer/queries/create/?play_id={self._url_data["play_id"]}'

    def set_title(self, title):
        field = self._driver.find_element_by_name("title")
        field.send_keys(title)

    def set_description(self, description):
        field = self._driver.find_element_by_name("description")
        field.send_keys(description)

    def click_save(self):
        self._submit("Save")
        return self._check_url_and_return_page(QueryDetailPage)


class QueryDetailPage(_BaseExplorerPage):
    _url_regex = r"/data-explorer/queries/(?P<query_id>\d+)/"

    @property
    def _url_path(self):
        return f"/data-explorer/queries/{self._url_data['query_id']}/"

    def read_title(self):
        return self._get_input_field("Title").get_attribute("value")

    def read_description(self):
        return self._get_input_field("Description").get_attribute("value")

    def read_sql(self):
        return self._get_input_field("SQL").get_attribute("value")

    def click_edit(self):
        self._submit("Edit SQL")

        home_page = HomePage(driver=self._driver, base_url=self._base_url)

        return home_page


class QueryLogPage(_BaseExplorerPage):
    _url_path = "/data-explorer/logs/"
