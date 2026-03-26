"""
LangChain Tool wrapper for the LinkedIn scraper.
This bridges Playwright scraping ↔ LangChain agent world.
"""

import asyncio
import json
from langchain_core.tools import tool

from scrapers.linkedin_scraper import LinkedInScraper


@tool
def search_linkedin_jobs(query: str = "full stack developer") -> str:
    """
    Search LinkedIn for public job listings matching the given query.
    Returns a JSON string with job titles and URLs.

    Args:
        query: The job search keywords, e.g. 'full stack developer'
    """
    scraper = LinkedInScraper()
    result = asyncio.run(scraper.scrape(keywords=query))

    # Return only title + url as requested
    output = [
        {"title": job.title, "url": job.url}
        for job in result.jobs
    ]
    return json.dumps(output, indent=2)
