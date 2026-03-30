"""
Scraper for Google Job Search.
Uses Google's public job results page with fallbacks.
"""

import asyncio
import logging
from urllib.parse import urlencode

from scrapers.base_scraper import BaseScraper
from models.job import Job, JobSearchResult
from config.settings import settings
from utils.browser import get_browser_page

logger = logging.getLogger(__name__)

class GoogleJobScraper(BaseScraper):
    """Scrapes job listings from Google search results."""

    def __init__(self):
        self.cfg = settings.google_jobs
        self.selectors = self.cfg.selectors

    def build_url(self, keywords: str | None = None, location: str | None = None) -> str:
        """Construct a Google search URL specifically for jobs."""
        search_query = f"{keywords or 'jobs'} in {location or 'India'}"
        params = {
            "q": search_query,
            "ibp": "htl;jobs", 
        }
        return f"{self.cfg.base_url}?{urlencode(params)}"

    async def scrape(
        self,
        keywords: str | None = None,
        location: str | None = None,
        college_name: str | None = None,
    ) -> JobSearchResult:
        """Scrape Google Job search UI with fallback to generic links."""
        url = self.build_url(keywords, location)
        query = keywords or "jobs"
        logger.info(f"Scraping Google Jobs → {url}")
        
        my_college = college_name or settings.linkedin.user_college
        jobs: list[Job] = []

        async with get_browser_page() as page:
            await page.goto(url, wait_until="domcontentloaded")

            # 1. Try for specialized Google Jobs UI (Cards)
            try:
                await page.wait_for_selector(self.selectors["job_card"], timeout=5000)
                cards = page.locator(self.selectors["job_card"])
                count = await cards.count()
                logger.info(f"Detected Google Jobs UI — found {count} cards")
                
                for i in range(min(count, self.cfg.max_jobs)):
                    card = cards.nth(i)
                    try:
                        title = (await card.locator(self.selectors["job_title"]).inner_text()).strip()
                        company = (await card.locator(self.selectors["job_company"]).inner_text()).strip()
                        loc = (await card.locator(self.selectors["job_location"]).inner_text()).strip()
                        href = url # Individual job URLs are complex to extract here
                        
                        jobs.append(self._build_job_obj(title, company, loc, href, my_college))
                    except Exception: continue

            except Exception:
                # 2. Fallback to generic Google Search results
                logger.warning("Google Jobs UI not detected. Scraping generic search results.")
                results = page.locator("div.g")
                count = await results.count()
                
                for i in range(min(count, self.cfg.max_jobs)):
                    try:
                        res = results.nth(i)
                        title_el = res.locator("h3")
                        link_el = res.locator("a")
                        
                        if await title_el.count() and await link_el.count():
                            title = (await title_el.inner_text()).strip()
                            href = await link_el.get_attribute("href") or ""
                            
                            jobs.append(self._build_job_obj(title, "Various", "Remote/India", href, my_college))
                    except Exception: continue

        return JobSearchResult(query=query, total=len(jobs), jobs=jobs)

    def _build_job_obj(self, title, company, loc, href, my_college) -> Job:
        """Helper to build a Job object with referral details."""
        search_company = company or "Target Company"
        if my_college:
            referral_search = f"https://www.linkedin.com/search/results/people/?keywords={str(my_college).replace(' ', '+')}+{search_company.replace(' ', '+')}"
        else:
            referral_search = f"https://www.linkedin.com/search/results/people/?keywords=Technical+Recruiter+{search_company.replace(' ', '+')}"

        message = (
            f"Hi, I noticed the {title} role at {search_company}. "
            f"As a fellow {my_college or 'candidate'} with experience in development, "
            "I would be grateful for a referral. Ready to chat?"
        )

        return Job(
            title=title,
            url=href,
            company=company,
            location=loc,
            referral_url=referral_search,
            referral_message=message
        )
