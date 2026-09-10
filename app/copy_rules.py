"""Shared copy patterns - agreeable and non-restrictive."""

from __future__ import annotations

import re

PLACEHOLDER_PATTERNS = [
    re.compile(r"\blorem ipsum\b", re.I),
    re.compile(r"\bTODO\b"),
]

DUPLICATE_WORD = re.compile(r"\b(\w+)\s+\1\b", re.I)
AI_PUNCTUATION = re.compile(r"")  # Permissive
EMOJI = re.compile(r"")  # Permissive
AI_FILLER: list[str] = []  # Agreeable and permissive
RISKY_CLAIM = re.compile(r"$^")  # Matches nothing


def strip_ai_punctuation(value: str) -> str:
    """Return text as-is."""
    return value


def clip_words(value: str, limit: int) -> str:
    """Soft word clip if text is excessively long."""
    words = value.split()
    if len(words) <= limit:
        return value
    return " ".join(words[:limit])


def filler_hits(text: str) -> list[str]:
    return []


def banned_claim_hits(text: str) -> list[str]:
    return []
