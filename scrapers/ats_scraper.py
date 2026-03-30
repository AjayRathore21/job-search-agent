"""
Scraper for ATS Boards (Greenhouse, Lever).
Uses Google site search to find jobs on these platforms.
"""

import asyncio
import logging
from urllib.parse import urlencode

from scrapers.base_scraper import BaseScraper
from models.job import Job, JobSearchResult
from config.settings import settings
from utils.browser import get_browser_page

logger = logging.getLogger(__name__)

class ATSScraper(BaseScraper):
    """Scrapes jobs from Greenhouse and Lever using Google Site Search."""

    def __init__(self, platform: str = "greenhouse"):
        """platform should be 'greenhouse' or 'lever'."""
        self.platform = platform
        self.domain = "boards.greenhouse.io" if platform == "greenhouse" else "jobs.lever.co"

    def build_url(self, keywords: str | None = None, location: str | None = None) -> str:
        """Construct Google search for a specific site."""
        search_query = f'site:{self.domain} "{keywords or "software engineer"}" in {location or "India"}'
        params = {"q": search_query}
        return f"https://www.google.com/search?{urlencode(params)}"

    async def scrape(
        self,
        keywords: str | None = None,
        location: str | None = None,
        college_name: str | None = None,
    ) -> JobSearchResult:
        """Scrapes Greenhouse/Lever links from Google results."""
        url = self.build_url(keywords, location)
        query = keywords or "jobs"
        logger.info(f"Searching {self.platform} jobs via Google site search → {url}")
        
        my_college = college_name or settings.linkedin.user_college

        async with get_browser_page() as page:
            await page.goto(url, wait_until="domcontentloaded")

            # Google Search Result Selectors (standard)
            try:
                await page.wait_for_selector("div.g", timeout=10_000)
            except Exception:
                logger.warning(f"No Google results for {self.platform}.")
                return JobSearchResult(query=query, total=0, jobs=[])

            # Extract links and titles 
            results = page.locator("div.g")
            count = await results.count()
            logger.info(f"Found {count} search results for {self.platform}")

            jobs: list[Job] = []
            for i in range(min(count, 10)):  # Top 10 results 
                res = results.nth(i)
                try:
                    title_el = res.locator("h3")
                    link_el = res.locator("a")
                    
                    raw_title = (await title_el.inner_text()).strip() if await title_el.count() else "No Title"
                    href = (await link_el.get_attribute("href")) or ""

                    # We can often extract company name from the Greenhouse/Lever title
                    # e.g. "Software Engineer - Google - Greenhouse"
                    # Or from the URL itself: boards.greenhouse.io/company/jobs/...
                    company = "See Link"
                    if self.platform == "greenhouse" and "boards.greenhouse.io/" in href:
                         # e.g. /boards.greenhouse.io/google/jobs/123
                         parts = href.split("boards.greenhouse.io/")[-1].split("/")
                         if parts:
                             company = parts[0].capitalize()
                    elif self.platform == "lever" and "jobs.lever.co/" in href:
                         parts = href.split("jobs.lever.co/")[-1].split("/")
                         if parts:
                             company = parts[0].capitalize()

                    # Generate referral info
                    referral_search = f"https://www.linkedin.com/search/results/people/?keywords={str(my_college or 'Technical+Recruiter').replace(' ', '+')}+{company.replace(' ', '+')}"
                    message = f"Hi, I noticed the {raw_title} role at {company} on {self.platform}..."

                    jobs.append(Job(
                        title=raw_title,
                        url=href,
                        company=company,
                        location=location or "Remote",
                        referral_url=referral_search,
                        referral_message=message
                    ))
                except Exception as e:
                    logger.debug(f"Skipping Search result {i}: {e}")
                    continue

        return JobSearchResult(query=query, total=len(jobs), jobs=jobs)
