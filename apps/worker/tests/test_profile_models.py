import pytest
from pydantic import ValidationError

from jobmatch_worker.profiles.models import CandidateProfile


def test_candidate_profile_requires_roles_and_skills() -> None:
    profile = CandidateProfile.model_validate(
        {
            "name": "Ada",
            "current_role": "Data Engineer",
            "seniority": "mid",
            "target_roles": ["Data Engineer"],
            "skills": ["Python", "SQL"],
            "experience_years": 4.0,
            "languages": ["English", "Indonesian"],
            "education": ["BSc Computer Science"],
        }
    )
    assert profile.target_roles == ["Data Engineer"]

    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"name": "Ada", "target_roles": [], "skills": []})