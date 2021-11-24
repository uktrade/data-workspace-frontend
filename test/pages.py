import asyncio

from pyppeteer import launch
from pyppeteer.browser import Browser


async def get_browser() -> Browser:
    browser = await launch(
        headless=True,
        executablePath="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-gpu"],
    )
    return browser


class _BasePage:
    _url_path = ""

    def __init__(self, browser: Browser, base_url="http://dataworkspace.test:8000", page=None):
        self._browser = browser
        self._page = page
        self._base_url = base_url

    @property
    def url(self) -> str:
        return self._base_url + self._url_path

    async def open(self):
        self._page = await self._browser.newPage()
        await self._page.goto(self.url)
        return self

    async def get_html(self) -> str:
        return await self._page.content()


class HomePage(_BasePage):
    _url_path = "/"

    async def toggle_filter(self, label) -> "_BasePage":
        if not self._page:
            await self.open()

        element = (
            await self._page.xpath(f"//input[@id = //label[contains(text(), '{label}')]/@for]")
        )[0]
        await asyncio.gather(
            self._page.waitForNavigation(),
            element.click(),
        )
        return self
