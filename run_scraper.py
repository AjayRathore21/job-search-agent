"""
Run the LinkedIn scraper directly — no LLM needed.
"""

import asyncio
import json
import logging

from scrapers.linkedin_scraper import LinkedInScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def main():
    scraper = LinkedInScraper()
    result = await scraper.scrape(keywords="full stack developer")

    # Output only title + url as JSON
    output = [{"title": job.title, "url": job.url} for job in result.jobs]

    print("\n" + "=" * 60)
    print(f"📋 Found {len(output)} jobs")
    print("=" * 60)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
