from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["skill", "experience", "education", "location", "seniority", "language"]
Criticality = Literal["must", "preferred", "nice"]


class JobRequirement(BaseModel):
    category: Category
    value: str = Field(min_length=1)
    criticality: Criticality
    evidence: str = Field(min_length=1)


class JobRequirements(BaseModel):
    requirements: list[JobRequirement] = Field(min_length=1)


__all__ = ["Category", "Criticality", "JobRequirement", "JobRequirements"]