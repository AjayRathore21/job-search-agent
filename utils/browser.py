"""
Browser lifecycle manager.
Provides a reusable async context manager so every scraper
doesn't have to deal with launch/close boilerplate.
"""

from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config.settings import settings


@asynccontextmanager
async def get_browser_page():
    """
    Yields a ready-to-use Playwright Page.

    Usage:
        async with get_browser_page() as page:
            await page.goto("https://example.com")
    """
    pw = await async_playwright().start()
    browser: Browser = await pw.chromium.launch(
        headless=settings.browser.headless,
        slow_mo=settings.browser.slow_mo,
    )
    context: BrowserContext = await browser.new_context(
        viewport=settings.browser.viewport,
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    context.set_default_timeout(settings.browser.timeout)
    page: Page = await context.new_page()

    try:
        yield page
    finally:
        await context.close()
        await browser.close()
        await pw.stop()
