"""Versioned keys for cached job-requirement extraction."""

import hashlib

MAX_REQUIREMENT_TEXT_CHARS = 100_000
_REQUIREMENTS_CACHE_VERSION = "requirements-v2"


def requirements_cache_key(description: str) -> str:
    """Return the stable cache key for the complete description and extractor version."""

    versioned_description = f"{_REQUIREMENTS_CACHE_VERSION}\0{description}"
    return hashlib.sha256(versioned_description.encode("utf-8")).hexdigest()


__all__ = ["MAX_REQUIREMENT_TEXT_CHARS", "requirements_cache_key"]
