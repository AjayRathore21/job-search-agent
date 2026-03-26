"""
Abstract base scraper.
Every new scraper inherits from this so the interface stays consistent.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseScraper(ABC):
    """
    Contract that all scrapers must follow.
    This makes it trivial to add new scrapers (e.g., Indeed, Naukri)
    without touching the rest of the codebase.
    """

    @abstractmethod
    async def scrape(self, **kwargs) -> Any:
        """Run the scraping logic and return structured data."""
        ...

    @abstractmethod
    def build_url(self, **kwargs) -> str:
        """Construct the target URL from parameters."""
        ...
