"""Evidence-backed match explanations and recommendations.

Recommendations are post-validated against verified candidate facts: any
recommendation that asserts a skill, certification, employer, degree,
language, or experience duration not present in the candidate profile is
either converted into conditional phrasing or dropped. This enforces the
no-fabrication rule; the LLM never adds claims the data does not support.
"""

import re
from typing import Any

from jobmatch_worker.matching.models import JobRequirement
from jobmatch_worker.profiles.models import CandidateProfile

CONDITIONAL_EXPERIENCE_PHRASE = (
    "If you have experience that is missing from the CV, "
    "add the verified project details to it."
)

_ASSERTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(\w[\w.+#-]*)\s+(?:years?|months?|yrs?|mos?)\s+"
            r"(?:of\s+)?(?:(\w[\w.+#-]*)\s+)?experience"
        ),
        "experience",
    ),
    (re.compile(r"(\w[\w.+#-]*)\s+experience\b"), "experience"),
    (re.compile(r"experience\s+(?:with|in)\s+(\w[\w.+#-]*)"), "experience"),
    (re.compile(r"(\w[\w.+#-]*)\s+certification\b"), "certification"),
    (re.compile(r"certified\s+(\w[\w.+#-]*)"), "certification"),
    (re.compile(r"(\w[\w.+#-]*)\s+certificate\b"), "certification"),
    (re.compile(r"(\w[\w.+#-]*)\s+degree\b"), "degree"),
    (re.compile(r"degree\s+in\s+(\w[\w.+#-]*)"), "degree"),
    (re.compile(r"(\w[\w.+#-]*)\s+proficiency\b"), "language"),
    (re.compile(r"(?:knowledge|proficiency|proficient)\s+(?:in|of)\s+(\w[\w.+#-]*)"), "language"),
    (re.compile(r"\bat\s+([A-Z][\w.+#-]*)"), "employer"),
)


def _verified_terms(candidate: CandidateProfile | dict[str, Any]) -> set[str]:
    if isinstance(candidate, CandidateProfile):
        facts = candidate.model_dump(mode="json")
    else:
        facts = candidate
    values: list[str] = []
    for key in ("skills", "languages", "education", "target_roles"):
        values.extend(facts.get(key) or [])
    for key in ("current_role", "name"):
        if facts.get(key):
            values.append(str(facts[key]))
    if facts.get("experience_years") is not None:
        years = int(float(facts["experience_years"]))
        values.extend([f"{years} years", f"{years} year"])
    return {token.casefold() for value in values for token in re.findall(r"[a-z0-9.+#-]+", value.casefold())}


_DURATION_WORDS = {"year", "years", "month", "months", "yrs", "mos", "of"}


def _asserted_entities(text: str) -> dict[str, set[str]]:
    """Entities claimed by a recommendation, grouped by claim type."""
    casefolded = text.casefold()
    found: dict[str, set[str]] = {}
    for pattern, claim_type in _ASSERTION_PATTERNS:
        for match in pattern.finditer(text if claim_type == "employer" else casefolded):
            if claim_type == "experience" and match.lastindex == 1:
                before = casefolded[: match.start(1)].strip()
                if before and before.rsplit(" ", 1)[-1] in _DURATION_WORDS:
                    continue
            if claim_type == "experience" and match.lastindex == 2:
                found.setdefault(claim_type, set()).add(match.group(1).casefold())
                found.setdefault(claim_type, set()).add(match.group(2).casefold())
            else:
                found.setdefault(claim_type, set()).add(match.group(1).casefold())
    return found


def sanitize_recommendations(
    candidate: CandidateProfile | dict[str, Any],
    recommendations: list[str],
) -> list[str]:
    """Drop unverifiable claims; convert experience-only claims to conditional phrasing."""
    verified = _verified_terms(candidate)
    sanitized: list[str] = []
    seen: set[str] = set()
    for text in recommendations:
        asserted = _asserted_entities(text)
        unverified = {
            entity
            for entities in asserted.values()
            for entity in entities
            if entity not in verified
        }
        if not unverified:
            recommendation = text
        elif set(asserted) == {"experience"}:
            recommendation = CONDITIONAL_EXPERIENCE_PHRASE
        else:
            continue
        if recommendation not in seen:
            sanitized.append(recommendation)
            seen.add(recommendation)
    return sanitized


def build_explanation_input(
    *,
    candidate: CandidateProfile,
    requirements: list[JobRequirement],
    dimension_scores: dict[str, int],
    strengths: list[str],
    gaps: list[str],
    critical_gaps: list[str],
) -> dict[str, Any]:
    """Structured facts for the explanation call; raw job text is never sent."""
    return {
        "candidate_profile": candidate.model_dump(mode="json"),
        "job_requirements": [r.model_dump(mode="json") for r in requirements],
        "dimension_scores": dimension_scores,
        "strengths": strengths,
        "gaps": gaps,
        "critical_gaps": critical_gaps,
        "instruction": (
            "The dimension scores above are authoritative and must not be changed. "
            "Provide a concise explanation and evidence-backed recommendations "
            "grounded only in the candidate profile and job requirements above."
        ),
    }


__all__ = [
    "CONDITIONAL_EXPERIENCE_PHRASE",
    "build_explanation_input",
    "sanitize_recommendations",
]
