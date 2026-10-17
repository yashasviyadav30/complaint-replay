"""The widget in a real browser: speaks the visitor's language, files a report, and shows its status later."""

import asyncio
import os
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.async_api import async_playwright

from replay.project import free_port

# The shop page is served from the service's own origin: Chrome blocks public pages from loading loopback scripts.
SHOP_PATH = "/test-shop"


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    port = free_port()
    env = {**os.environ, "START_LIVE_SHOP": "0", "NVIDIA_API_KEY": "", "NEBIUS_API_KEY": "",
           "DATABASE_URL": f"sqlite:///{tmp_path_factory.mktemp('db') / 'db.sqlite'}"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.app:app", "--port", str(port),
                             "--log-level", "warning"], env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/v1/me", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


async def visit(service: str, locale: str) -> dict:
    page_html = (f'<!doctype html><html><body><h1>Shop</h1>'
                 f'<script src="{service}/widget.js" data-project="demo"></script></body></html>')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context(locale=locale)).new_page()
        await page.route(service + SHOP_PATH, lambda route: route.fulfill(status=200, content_type="text/html", body=page_html))
        await page.goto(service + SHOP_PATH)
        button = page.locator("#cr-widget > button")
        seen = {"button": await button.inner_text(), "dir": await page.locator("#cr-widget").get_attribute("dir")}
        await button.click()
        await page.locator("#cr-text").fill("الزر لا يعمل")
        await page.locator("#cr-widget button[type=submit]").click()
        await page.wait_for_function("localStorage.getItem('crp-reports') !== null")
        await page.locator("#cr-widget > button").click()
        await page.locator("#cr-widget .status:not([hidden])").wait_for(timeout=5000)
        seen["status"] = await page.locator("#cr-widget .status").inner_text()
        await browser.close()
    return seen


def test_arabic_visitor_gets_an_arabic_rtl_widget_and_sees_their_report_status(service) -> None:
    seen = asyncio.run(visit(service, "ar-EG"))
    assert seen["button"] == "الإبلاغ عن مشكلة" and seen["dir"] == "rtl"
    assert seen["status"].startswith("بلاغك الأخير")


def test_a_fixed_report_links_the_reporter_to_the_film_of_it_working(service) -> None:
    async def run() -> dict:
        page_html = f'<!doctype html><html><body><script src="{service}/widget.js" data-project="demo"></script></body></html>'
        fixed = '{"status": "fixed", "reports": 1, "films": {"after": "/shots/c1-after.gif"}}'
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await (await browser.new_context(locale="hi-IN")).new_page()
            await page.route(service + SHOP_PATH, lambda r: r.fulfill(status=200, content_type="text/html", body=page_html))
            await page.route("**/api/v1/reports/*", lambda r: r.fulfill(status=200, content_type="application/json", body=fixed))
            await page.goto(service + SHOP_PATH)
            await page.evaluate("localStorage.setItem('crp-reports', JSON.stringify([{id: 'r1', token: 't'}]))")
            await page.locator("#cr-widget > button").click()
            link = page.locator("#cr-widget .status a")
            await link.wait_for(timeout=5000)
            seen = {"text": await link.inner_text(), "href": await link.get_attribute("href")}
            await browser.close()
        return seen

    seen = asyncio.run(run())
    assert seen["text"] == "अब इसे ठीक चलते हुए देखें" and seen["href"] == service + "/shots/c1-after.gif"

