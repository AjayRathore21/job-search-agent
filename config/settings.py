"""
Centralized configuration for the scraper project.
All settings (timeouts, URLs, selectors) live here so scrapers stay clean.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BrowserConfig:
    """Playwright browser launch settings."""
    headless: bool = True
    slow_mo: int = 0  # ms delay between actions (useful for debugging)
    timeout: int = 30_000  # default navigation timeout in ms
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 800})


@dataclass
class LinkedInConfig:
    """LinkedIn-specific scraper settings."""
    base_url: str = "https://www.linkedin.com/jobs/search"
    default_keywords: str = "full stack developer"
    default_location: str = "India"
    max_jobs: int = 25
    scroll_pause: float = 1.5  # seconds to wait after each scroll
    user_college: str | None = "Guru Jambheshwar University of Science and Technology"

    # CSS selectors — update these if LinkedIn changes its markup
    selectors: Dict[str, str] = field(default_factory=lambda: {
        "job_card": "ul.jobs-search__results-list li",
        "job_title": "h3.base-search-card__title",
        "job_link": "a.base-card__full-link",
        "job_company": "h4.base-search-card__subtitle",
        "job_location": "span.job-search-card__location",
        "show_more_btn": "button.infinite-scroller__show-more-btn",
    })


@dataclass
class GoogleJobConfig:
    """Settings for Google Job Search scraper."""
    base_url: str = "https://www.google.com/search"
    max_jobs: int = 15
    selectors: Dict[str, str] = field(default_factory=lambda: {
        "job_card": "div.iS7Hke",
        "job_title": "div.BjS7Rb",
        "job_company": "div.vNEEBe",
        "job_location": "div.Q8Z6Ec",
        "job_link": "a.M89U9e",
    })

@dataclass
class GreenhouseConfig:
    """Settings for Greenhouse ATS board searches."""
    base_url: str = "https://boards.greenhouse.io/"
    # Scrapers for ATS often target specific company boards

@dataclass
class Settings:
    """Root settings object."""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    linkedin: LinkedInConfig = field(default_factory=LinkedInConfig)
    google_jobs: GoogleJobConfig = field(default_factory=GoogleJobConfig)
    greenhouse: GreenhouseConfig = field(default_factory=GreenhouseConfig)


# Singleton settings instance used across the project
settings = Settings()
