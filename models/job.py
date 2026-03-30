"""
Pydantic models for structured job data.
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional


class Job(BaseModel):
    """Represents a single job listing."""
    title: str
    url: str
    company: Optional[str] = None
    location: Optional[str] = None
    referral_url: Optional[str] = None
    referral_message: Optional[str] = None


class JobSearchResult(BaseModel):
    """Wrapper for a collection of scraped jobs."""
    query: str
    total: int
    jobs: list[Job]
