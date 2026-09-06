"""The All Elite design system: load once, inject everywhere.

This is the answer to "stop repeating yourself in prompts". Rules live in
``design-system/principles/principles.json`` and are compiled into a compact
block that every Claude stage receives. A flyer request then only has to carry
what is *different* about that flyer.

Rules are classified:

* ``hard``     - follow essentially every time; a violation is a QA error
* ``soft``     - follow by default; may be broken with a stated reason
* ``optional`` - a technique for appropriate campaigns, never universal
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import get_settings
from .logging_setup import get_logger

log = get_logger(__name__)

FILES = {
    "principles": "principles/principles.json",
    "preferences": "preferences/preferences.json",
    "successful": "patterns/successful-patterns.json",
    "failures": "failures/failed-patterns.json",
}

# Which rule sections each pipeline stage actually needs. Sending the whole
# system to every stage is exactly the bloat this module exists to prevent.
STAGE_SECTIONS: dict[str, tuple[str, ...]] = {
    "planner": ("global", "composition_archetypes"),
    "copywriter": ("global", "copywriting", "typography", "branding", "product_presentation"),
    "designer": (
        "global",
        "photography",
        "composition_archetypes",
        "typography",
        "color",
        "branding",
        "iconography",
        "product_presentation",
        "social",
    ),
    "qa": ("global", "photography", "typography", "color", "branding", "social"),
    "reference": ("composition_archetypes", "photography", "typography", "color"),
    "distiller": ("global",),
}


def _root() -> Path:
    return get_settings().paths.design_system


@lru_cache(maxsize=8)
def _load(name: str) -> dict[str, Any]:
    path = _root() / FILES[name]
    if not path.exists():
        log.warning("Design-system file missing: %s", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("Design-system file %s is not valid JSON: %s", path, exc)
        return {}


def clear_cache() -> None:
    _load.cache_clear()


def principles() -> dict[str, Any]:
    return _load("principles")


def preferences() -> dict[str, Any]:
    return _load("preferences")


def failures() -> dict[str, Any]:
    return _load("failures")


def successful_patterns() -> dict[str, Any]:
    return _load("successful")


# ------------------------------------------------------------------ lookups


def archetypes() -> list[dict]:
    return principles().get("composition_archetypes", [])


def archetype_for_layout(layout: str) -> dict | None:
    return next((a for a in archetypes() if a.get("layout") == layout), None)


def archetype(archetype_id: str) -> dict | None:
    return next((a for a in archetypes() if a.get("id") == archetype_id), None)


def layout_for_archetype(archetype_id: str) -> str | None:
    found = archetype(archetype_id)
    return found.get("layout") if found else None


def client_defaults(client_id: str) -> dict:
    return preferences().get("client_defaults", {}).get(client_id, {})


def hard_rules(section: str) -> list[str]:
    return [r["rule"] for r in principles().get(section, []) if r.get("class") == "hard"]


def never_list() -> list[str]:
    return [item["rule"] for item in failures().get("never", [])]


# ------------------------------------------------------------------ compiling


def _render_rules(section: str) -> str:
    entries = principles().get(section, [])
    if not entries:
        return ""
    if section == "composition_archetypes":
        lines = []
        for item in entries:
            lines.append(
                f"- **{item['id']}** (layout `{item['layout']}`) - {item['use_case']}. "
                f"Image: {item['image_hierarchy']}. Density: {item['text_density']}. "
                f"CTA: {item['cta']}. Treatment: {item['treatment']}"
            )
        return "\n".join(lines)
    return "\n".join(f"- [{r.get('class', 'soft').upper()}] {r['rule']}" for r in entries)


SECTION_TITLES = {
    "global": "Global rules",
    "photography": "Photography",
    "composition_archetypes": "Composition archetypes",
    "typography": "Typography",
    "color": "Colour",
    "branding": "Branding",
    "copywriting": "Copywriting",
    "iconography": "Iconography",
    "product_presentation": "Product presentation",
    "social": "Social / format",
}


def compile_for_stage(stage: str, client_id: str | None = None) -> str:
    """The design-system block injected into a stage's system prompt."""
    sections = STAGE_SECTIONS.get(stage, ("global",))
    blocks: list[str] = []

    for section in sections:
        body = _render_rules(section)
        if body:
            blocks.append(f"### {SECTION_TITLES.get(section, section)}\n{body}")

    never = never_list()
    if never:
        blocks.append("### Never / avoid\n" + "\n".join(f"- {item}" for item in never))

    test = principles().get("human_design_test", {})
    if test and stage in {"designer", "qa"}:
        checks = "\n".join(f"- {c}" for c in test.get("checks", []))
        fails = ", ".join(test.get("fail_if_it_resembles", []))
        blocks.append(
            f"### The human design test\n**{test.get('question', '')}**\n{checks}\n"
            f"\nFail it if it resembles: {fails}."
        )

    if client_id:
        defaults = client_defaults(client_id)
        if defaults:
            blocks.append(
                "### This client's established preferences\n"
                + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in defaults.items())
            )

    declared = [p for p in preferences().get("declared", []) if p.get("weight", 0) >= 0.8]
    if declared and stage in {"designer", "copywriter", "planner"}:
        blocks.append(
            "### Standing operator preferences\n"
            + "\n".join(f"- {p['statement']}" for p in declared)
        )

    learned = successful_patterns().get("patterns", [])
    if learned and stage in {"designer", "copywriter"}:
        blocks.append(
            "### Patterns proven on approved work\n"
            + "\n".join(f"- {p.get('rule', p)}" for p in learned[:12])
        )

    if not blocks:
        return ""

    return (
        "<design_system>\n"
        "These are the standing rules for this operation. They were defined once "
        "and apply to every flyer; the request itself only carries what is "
        "different about today's flyer.\n\n" + "\n\n".join(blocks) + "\n</design_system>"
    )


def summary() -> dict[str, int]:
    return {
        "hard_rules": sum(
            1
            for section in principles().values()
            if isinstance(section, list)
            for r in section
            if isinstance(r, dict) and r.get("class") == "hard"
        ),
        "soft_rules": sum(
            1
            for section in principles().values()
            if isinstance(section, list)
            for r in section
            if isinstance(r, dict) and r.get("class") == "soft"
        ),
        "archetypes": len(archetypes()),
        "never_rules": len(never_list()),
        "declared_preferences": len(preferences().get("declared", [])),
        "learned_patterns": len(successful_patterns().get("patterns", [])),
        "corpus_successful": successful_patterns().get("corpus_size", 0),
        "corpus_failed": failures().get("corpus_size", 0),
    }
