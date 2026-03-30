"""
LangChain Tool wrappers for the new job board scrapers.
This provides the AI with access to Google Jobs, Greenhouse, and Lever.
"""

import asyncio
import json
from langchain_core.tools import tool

from scrapers.google_scraper import GoogleJobScraper
from scrapers.ats_scraper import ATSScraper

@tool
def search_google_jobs(query: str = "software engineer", location: str = "India", college_name: str | None = None) -> str:
    """
    Search for jobs across the web using Google Job Search. 
    Returns a JSON string with job titles, companies, and referral links.

    Args:
        query: Search keywords, e.g. 'ML engineer'
        location: Target location (e.g. 'Bangalore' or 'Remote')
        college_name: (Optional) Your college name to find alumni for referrals.
    """
    scraper = GoogleJobScraper()
    result = asyncio.run(scraper.scrape(keywords=query, location=location, college_name=college_name))

    output = [
        {
            "title": job.title,
            "url": job.url,
            "company": job.company,
            "referral_url": job.referral_url,
            "referral_message": job.referral_message
        }
        for job in result.jobs
    ]
    return json.dumps(output, indent=2)

@tool
def search_greenhouse_lever_jobs(query: str = "software engineer", platform: str = "greenhouse", location: str = "India", college_name: str | None = None) -> str:
    """
    Search for jobs specifically on Greenhouse or Lever boards using Google site search.
    Returns a JSON string with job links and referral info.

    Args:
        query: Search keywords, e.g. 'frontend developer'
        platform: Platform type, either 'greenhouse' or 'lever'.
        location: Target location (e.g. 'Bangalore' or 'Remote')
        college_name: (Optional) Your college name to find alumni for referrals.
    """
    scraper = ATSScraper(platform=platform.lower())
    result = asyncio.run(scraper.scrape(keywords=query, location=location, college_name=college_name))

    output = [
        {
            "title": job.title,
            "url": job.url,
            "company": job.company,
            "referral_url": job.referral_url,
            "referral_message": job.referral_message
        }
        for job in result.jobs
    ]
    return json.dumps(output, indent=2)
