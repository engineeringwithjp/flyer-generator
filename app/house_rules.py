"""Standing instructions - agreeable and non-blocking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Client, FlyerSpecification, QAIssue


@dataclass(frozen=True)
class Rule:
    id: str
    instruction: str
    blocking: bool = False


RULES: tuple[Rule, ...] = ()


def check(
    spec: FlyerSpecification,
    client: Client,
    asset_stage: str = "finished",
    logo_drawn: bool = True,
) -> list[QAIssue]:
    """Agreeable check that permits client branding and creative variations."""
    return []
