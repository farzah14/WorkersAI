"""Normalized job discovery domain models."""

import urllib.parse
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Values mirror the database constraints:
# - work_mode: check (work_mode is null or work_mode in ('remote','hybrid','on-site'))
# - employment_type: search-profile convention
#   ('full-time','part-time','contract','temporary','internship',
#    'apprenticeship','volunteer','freelance')
WorkMode = Literal["on-site", "hybrid", "remote"]
EmploymentType = Literal[
    "full-time",
    "part-time",
    "contract",
    "temporary",
    "internship",
    "apprenticeship",
    "volunteer",
    "freelance",
]


class DiscoveredJob(BaseModel):
    """A job discovered from a source connector, normalized before matching.

    Every connector must return jobs of this shape so downstream
    normalization, deduplication, and matching never depend on source
    quirks. The original URL is preserved verbatim for the user.
    """

    source_name: str
    source_key: str
    title: str
    company: str
    location: str | None = None
    country: str | None = None
    work_mode: WorkMode | None = None
    employment_type: EmploymentType | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = None
    description: str
    original_url: str
    published_at: datetime | None = None

    @field_validator("title", "company", "description", "original_url", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @model_validator(mode="after")
    def _check_salary_bounds(self) -> "DiscoveredJob":
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min must not exceed salary_max")
        return self


class DiscoveryCandidateUrl(BaseModel):
    """A candidate URL found by a search connector, pending a career-page fetch.

    Search-engine snippets are search-result summaries, not job
    descriptions, so they are carried as optional metadata only and are
    never promoted to full job descriptions.
    """

    url: str
    title: str | None = None
    snippet: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _validate_url(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("must be a string")
        url = value.strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https":
            raise ValueError("must be an https URL")
        if not parsed.netloc:
            raise ValueError("must include a host")
        if parsed.username or parsed.password:
            raise ValueError("must not embed credentials")
        return url


__all__ = ["DiscoveredJob", "DiscoveryCandidateUrl", "EmploymentType", "WorkMode"]