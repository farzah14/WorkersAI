from typing import Literal

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    name: str | None = None
    current_role: str | None = None
    seniority: Literal["intern", "junior", "mid", "senior", "lead", "manager", "executive", "unknown"] = "unknown"
    target_roles: list[str] = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    experience_years: float | None = Field(default=None, ge=0, le=80)
    languages: list[str] = []
    education: list[str] = []


__all__ = ["CandidateProfile"]