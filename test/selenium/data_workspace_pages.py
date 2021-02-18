from test.selenium.common import _BasePage


class _BaseDataWorkspacePage(_BasePage):
    pass


class MasterDatasetCataloguePage(_BaseDataWorkspacePage):
    _url_regex = r'/datasets/(?P<dataset_id>[A-Za-z0-9\-]{36})(?:\#.*)?'

    @property
    def _url_path(self):
        return f'/datasets/{self._url_data["dataset_id"]}'

    def click_code_snippets_and_columns_toggle(self, table_name):
        toggle = self._driver.find_element_by_xpath(
            f"//td[text() = '{table_name}']/../following-sibling::tr[1]//summary"
        )
        toggle.click()

    def click_copy_code(self, table_name, language):
        language_tab = self._driver.find_element_by_xpath(
            f"//td[text() = '{table_name}']/.."
            f"/following-sibling::tr[1]//a[normalize-space(text()) = '{language}']"
        )
        language_tab.click()

        copy_code_button = self._driver.find_element_by_xpath(
            f"//td[text() = '{table_name}']/.."
            f"/following-sibling::tr[1]//h3[normalize-space(text()) = '{language}']"
            f"/following-sibling::div//button[normalize-space(text()) = 'Copy code']"
        )
        copy_code_button.click()
