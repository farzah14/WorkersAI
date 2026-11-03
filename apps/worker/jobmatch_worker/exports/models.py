from __future__ import annotations

import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator

ExportFormat = Literal["xlsx", "pdf"]
ExportScope = Literal["all", "current_filters", "best_and_strong"]
ExportStatus = Literal["queued", "processing", "completed", "failed"]
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

MAX_QUERY_CODE_POINTS = 200
MAX_SOURCE_CODE_POINTS = 200
MAX_SOURCE_FILTERS = 20
MAX_EMPLOYMENT_FILTERS = 8


def normalize_query(value: str) -> str:
    """Normalize query text exactly like the dashboard's JavaScript helper.

    NFC, whitespace collapse, and Python ``lower()``. No ``casefold()``, accent
    removal, or transliteration so web and worker membership stay identical.
    """
    return " ".join(unicodedata.normalize("NFC", value).split()).lower()


class ExportFilters(BaseModel):
    """Validated export filter contract. Rejects arbitrary SQL-like fields."""

    model_config = {"extra": "forbid"}

    query: str | None = None
    region: list[str] | None = None
    work_mode: list[str] | None = None
    employment_type: list[EmploymentType] | None = None
    source_name: list[str] | None = None
    min_score: int | None = None
    status: list[str] | None = None
    exclude_ignored: StrictBool = False
    date_from: date | None = None
    date_to: date | None = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_query(value)
        if len(normalized) > MAX_QUERY_CODE_POINTS:
            raise ValueError("query_too_long")
        return normalized

    @field_validator("source_name")
    @classmethod
    def _validate_sources(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > MAX_SOURCE_FILTERS:
            raise ValueError("too_many_sources")
        normalized: list[str] = []
        for source in value:
            trimmed = source.strip()
            if not trimmed:
                raise ValueError("blank_source_name")
            if len(trimmed) > MAX_SOURCE_CODE_POINTS:
                raise ValueError("source_name_too_long")
            normalized.append(trimmed)
        return normalized

    @field_validator("employment_type")
    @classmethod
    def _bound_employment_types(
        cls, value: list[EmploymentType] | None
    ) -> list[EmploymentType] | None:
        if value is not None and len(value) > MAX_EMPLOYMENT_FILTERS:
            raise ValueError("too_many_employment_types")
        return value

    @model_validator(mode="after")
    def _check_date_range(self) -> ExportFilters:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("reversed_date_range")
        return self


class ExportRequest(BaseModel):
    export_id: str
    user_id: str
    search_run_id: str
    format: ExportFormat
    scope: ExportScope
    filters: ExportFilters | None = None


class CandidateSummary(BaseModel):
    name: str = ""
    headline: str = ""
    skills: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    location: str = ""
    languages: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class SearchCriteria(BaseModel):
    scope: ExportScope
    query: str | None = None
    region: list[str] | None = None
    work_mode: list[str] | None = None
    employment_type: list[str] | None = None
    source_name: list[str] | None = None
    min_score: int | None = None
    status: list[str] | None = None
    exclude_ignored: StrictBool = False
    date_from: date | None = None
    date_to: date | None = None


class ExportRow(BaseModel):
    job_title: str
    company: str
    location: str | None = None
    region: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_min: int | float | None = None
    salary_max: int | float | None = None
    currency: str | None = None
    published_at: date | None = None
    overall_score: float
    skills_score: float
    experience_score: float
    education_score: float
    location_score: float
    seniority_score: float
    language_score: float
    verdict: str
    status: str = "new"
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_name: str
    original_url: str
