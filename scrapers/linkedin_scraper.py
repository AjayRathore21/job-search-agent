"""
LinkedIn public jobs page scraper.
Works WITHOUT login — uses LinkedIn's public /jobs/search endpoint.
"""

import asyncio
import logging
from urllib.parse import urlencode

from scrapers.base_scraper import BaseScraper
from models.job import Job, JobSearchResult
from config.settings import settings
from utils.browser import get_browser_page

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scrapes LinkedIn's public job search results page."""

    def __init__(self):
        self.cfg = settings.linkedin
        self.selectors = self.cfg.selectors

    def build_url(self, keywords: str | None = None, location: str | None = None) -> str:
        """Build the LinkedIn search URL from query params."""
        params = {
            "keywords": keywords or self.cfg.default_keywords,
            "location": location or self.cfg.default_location,
        }
        return f"{self.cfg.base_url}?{urlencode(params)}"

    async def _scroll_to_load(self, page) -> None:
        """Scroll down incrementally to trigger lazy-loaded job cards."""
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(self.cfg.scroll_pause)

            # Click "Show more" button if it appears
            show_more = page.locator(self.selectors["show_more_btn"])
            if await show_more.is_visible():
                await show_more.click()
                await asyncio.sleep(self.cfg.scroll_pause)

    async def scrape(
        self,
        keywords: str | None = None,
        location: str | None = None,
    ) -> JobSearchResult:
        """
        Scrape LinkedIn public job listings.

        Args:
            keywords: Job search query (default: 'full stack developer')
            location: Location filter  (default: 'India')

        Returns:
            JobSearchResult with list of Job objects
        """
        url = self.build_url(keywords, location)
        query = keywords or self.cfg.default_keywords
        logger.info(f"Scraping LinkedIn jobs → {url}")

        async with get_browser_page() as page:
            await page.goto(url, wait_until="domcontentloaded")

            # Wait for job cards to render
            try:
                await page.wait_for_selector(
                    self.selectors["job_card"], timeout=15_000
                )
            except Exception:
                logger.warning("No job cards found — LinkedIn may have changed its markup.")
                return JobSearchResult(query=query, total=0, jobs=[])

            # Scroll to load more results
            await self._scroll_to_load(page)

            # Extract job data
            cards = page.locator(self.selectors["job_card"])
            count = await cards.count()
            logger.info(f"Found {count} job cards")

            jobs: list[Job] = []
            for i in range(min(count, self.cfg.max_jobs)):
                card = cards.nth(i)
                try:
                    title_el = card.locator(self.selectors["job_title"])
                    link_el = card.locator(self.selectors["job_link"])
                    company_el = card.locator(self.selectors["job_company"])
                    location_el = card.locator(self.selectors["job_location"])

                    title = (await title_el.inner_text()).strip()
                    href = await link_el.get_attribute("href") or ""
                    company = (await company_el.inner_text()).strip() if await company_el.count() else None
                    loc = (await location_el.inner_text()).strip() if await location_el.count() else None

                    if title and href:
                        jobs.append(Job(
                            title=title,
                            url=href.split("?")[0],  # strip tracking params
                            company=company,
                            location=loc,
                        ))
                except Exception as exc:
                    logger.debug(f"Skipping card {i}: {exc}")
                    continue

        result = JobSearchResult(query=query, total=len(jobs), jobs=jobs)
        logger.info(f"Scraped {result.total} jobs for '{query}'")
        return result
