"""Shared copy patterns.

Lives outside both ``app.ai`` and ``app.pipeline`` so the copywriter and the QA
gate can agree on one definition without importing each other.
"""

from __future__ import annotations

import re

# --- Placeholder / unfinished text -----------------------------------------
PLACEHOLDER_PATTERNS = [
    re.compile(r"\blorem ipsum\b", re.I),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\byour (?:company|business) name\b", re.I),
    re.compile(r"\bxxx+\b", re.I),
    re.compile(r"\{\{.*?\}\}"),
    re.compile(r"\[[a-z_ ]+\]", re.I),
    re.compile(r"555-?01\d\d"),
]

DUPLICATE_WORD = re.compile(r"\b(\w+)\s+\1\b", re.I)

# --- "Does this read as AI-written?" ----------------------------------------
# Contractors' marketing does not use em dashes or emoji. Their presence is the
# fastest tell there is that a machine wrote the copy.
AI_PUNCTUATION = re.compile(r"[—–]")  # em dash, en dash

EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"  # pictographs, emoticons, symbols
    "\U00002600-\U000027bf"  # misc symbols and dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators
    "←-⇿"  # arrows
    "⬀-⯿"
    "️"  # variation selector
    "]"
)

AI_FILLER = [
    "unlock",
    "elevate your",
    "in today's",
    "look no further",
    "we've got you covered",
    "game-changer",
    "game changer",
    "seamless",
    "cutting-edge",
    "world-class",
    "unparalleled",
    "take your home to the next level",
    "peace of mind you deserve",
    "dive into",
    "in the realm of",
    "when it comes to",
    "rest assured",
    "second to none",
    "one-stop shop",
    "transform your home into",
]

# --- Claims a contractor can be reported for --------------------------------
# "Free Roof Inspection" and "Free Roof Estimate" are legitimate offers; a bare
# "free roof" is the storm-chaser claim regulators act on.
RISKY_CLAIM = re.compile(
    r"\b("
    r"guaranteed approval"
    r"|free roof(?!\s+(?:inspection|estimate|quote|consultation|check|assessment))"
    r"|insurance will pay"
    r"|no cost to you"
    r"|we guarantee your claim"
    r"|100% (?:free|guaranteed)"
    r"|get your roof approved"
    r")\b",
    re.I,
)


def strip_ai_punctuation(value: str) -> str:
    """Em/en dashes never reach the renderer, whatever a model returns."""
    return " ".join(value.replace("—", ",").replace("–", "-").split())


def clip_words(value: str, limit: int) -> str:
    """Trim to a length budget on a word boundary, never mid-word."""
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    head = value[:limit]
    # Only drop the trailing fragment when the budget actually landed mid-word.
    if value[limit] != " ":
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,;:.-") or value[:limit]


def filler_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in AI_FILLER if phrase in lowered]
