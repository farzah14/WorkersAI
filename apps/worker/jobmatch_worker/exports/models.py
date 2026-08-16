from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ExportFormat = Literal["xlsx", "pdf"]
ExportScope = Literal["all", "current_filters", "best_and_strong"]
ExportStatus = Literal["queued", "processing", "completed", "failed"]


class ExportFilters(BaseModel):
    """Validated export filter contract. Rejects arbitrary SQL-like fields."""

    model_config = {"extra": "forbid"}

    region: list[str] | None = None
    work_mode: list[str] | None = None
    min_score: int | None = None
    status: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None


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
    region: list[str] | None = None
    work_mode: list[str] | None = None
    min_score: int | None = None
    status: list[str] | None = None
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
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_name: str
    original_url: str