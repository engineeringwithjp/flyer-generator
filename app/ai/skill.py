"""Load the Claude Skill as the system prompt.

The markdown in ``.claude/skills/construction-flyer/`` is the single creative
and business instruction layer. It is read at runtime rather than duplicated in
Python, so editing a rule file changes behaviour with no code change - and the
same files are picked up by Claude Code when you work in the repo by hand.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from ..logging_setup import get_logger

log = get_logger(__name__)

# Loaded for every call.
CORE_DOCS = ("SKILL.md",)

# Loaded only by the stage that needs them, to keep prompts lean.
STAGE_DOCS: dict[str, tuple[str, ...]] = {
    "planner": ("construction-marketing.md",),
    "copywriter": ("copywriting-rules.md", "branding-rules.md"),
    "designer": (
        "design-rules.md",
        "photography-rules.md",
        "asset-selection.md",
        "branding-rules.md",
    ),
    "qa": ("quality-control.md", "negative-rules.md"),
    "reference": ("reference-analysis.md",),
    "distiller": ("SKILL.md",),
}


@lru_cache(maxsize=32)
def _read(name: str) -> str:
    path = get_settings().paths.skill / name
    if not path.exists():
        log.warning("Skill document missing: %s", path)
        return ""
    return path.read_text(encoding="utf-8").strip()


def system_prompt(stage: str, client_id: str | None = None) -> str:
    """Compose the system prompt for a pipeline stage.

    Three layers, in order of precedence:

    1. the Skill markdown (narrative instructions for this stage)
    2. the compiled design system (structured hard/soft rules + never list)
    3. the client's own established preferences
    """
    names: list[str] = []
    for name in (*CORE_DOCS, *STAGE_DOCS.get(stage, ())):
        if name not in names:
            names.append(name)

    sections = []
    for name in names:
        body = _read(name)
        if body:
            sections.append(f'<skill_document name="{name}">\n{body}\n</skill_document>')

    if not sections:  # pragma: no cover - only if the skill folder is deleted
        return (
            "You are a senior marketing designer for residential construction "
            "contractors. Produce concise, credible, high-contrast flyer content."
        )

    from ..design_system import compile_for_stage

    design_block = compile_for_stage(stage, client_id)
    if design_block:
        sections.append(design_block)

    return (
        "You are the creative engine of an automated construction-marketing system.\n"
        "The documents below are your operating instructions. Follow them exactly; "
        "they outrank any preference of your own.\n\n" + "\n\n".join(sections)
    )


def clear_cache() -> None:
    _read.cache_clear()
