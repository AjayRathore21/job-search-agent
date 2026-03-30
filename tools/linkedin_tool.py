"""
LangChain Tool wrapper for the LinkedIn scraper.
This bridges Playwright scraping ↔ LangChain agent world.
"""

import asyncio
import json
from langchain_core.tools import tool

from scrapers.linkedin_scraper import LinkedInScraper


@tool
def search_linkedin_jobs(query: str = "full stack developer", college_name: str | None = None) -> str:
    """
    Search LinkedIn for public job listings matching the given query.
    Returns a JSON string with job titles, URLs, and referral tips.

    Args:
        query: The job search keywords, e.g. 'full stack developer'
        college_name: (Optional) Your college name to find alumni for referrals.
    """
    scraper = LinkedInScraper()
    result = asyncio.run(scraper.scrape(keywords=query, college_name=college_name))

    # Return only title + url + referral info
    output = [
        {
            "title": job.title,
            "url": job.url,
            "referral_url": job.referral_url,
            "referral_message": job.referral_message
        }
        for job in result.jobs
    ]
    return json.dumps(output, indent=2)
