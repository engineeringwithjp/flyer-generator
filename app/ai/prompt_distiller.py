"""Prompt-to-Skill: turn a corpus of old prompts into a design system.

Reads ``design-system/historical-prompts/{successful,unsuccessful}/`` and asks
Claude to extract the *underlying rules* rather than the wording: deduplicate
repeated concepts, classify each rule hard / soft / optional, separate global
from campaign-specific from client-specific, and surface contradictions with a
proposed resolution.

Nothing is applied automatically. The output is a reviewable proposal in
``design-system/proposals/``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..config import get_settings
from ..errors import AIError
from ..logging_setup import get_logger
from .claude_client import ClaudeClient, compact_json, get_claude
from .skill import system_prompt

log = get_logger(__name__)

MAX_PROMPT_CHARS = 20_000

RULE = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "kebab-case, stable"},
        "scope": {
            "type": "string",
            "enum": ["global", "campaign", "client", "reference-influenced"],
        },
        "section": {
            "type": "string",
            "enum": [
                "global",
                "photography",
                "composition_archetypes",
                "typography",
                "color",
                "branding",
                "copywriting",
                "iconography",
                "product_presentation",
                "social",
            ],
        },
        "class": {"type": "string", "enum": ["hard", "soft", "optional"]},
        "rule": {"type": "string", "description": "One sentence, imperative, deduplicated"},
        "evidence_count": {
            "type": "integer",
            "description": "How many source prompts expressed this concept",
        },
        "applies_to": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Campaign or service ids, empty for global",
        },
    },
    "required": ["id", "scope", "section", "class", "rule", "evidence_count"],
    "additionalProperties": False,
}

DISTILL_SCHEMA = {
    "type": "object",
    "properties": {
        "extracted_rules": {"type": "array", "items": RULE},
        "never_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "copy",
                            "layout",
                            "photography",
                            "color",
                            "typography",
                            "iconography",
                            "branding",
                            "quality",
                        ],
                    },
                    "rule": {"type": "string"},
                    "observed_failure": {"type": "string"},
                },
                "required": ["id", "category", "rule"],
                "additionalProperties": False,
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "position_a": {"type": "string"},
                    "position_b": {"type": "string"},
                    "resolution": {"type": "string"},
                    "reason": {"type": "string"},
                    "needs_operator_decision": {"type": "boolean"},
                },
                "required": ["description", "position_a", "position_b", "resolution", "reason"],
                "additionalProperties": False,
            },
        },
        "not_promoted": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string"},
                    "why_not": {"type": "string"},
                },
                "required": ["instruction", "why_not"],
                "additionalProperties": False,
            },
            "description": "One-off instructions deliberately NOT made permanent",
        },
        "repetition_report": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "times_repeated": {"type": "integer"},
                    "collapsed_into": {"type": "string"},
                },
                "required": ["concept", "times_repeated", "collapsed_into"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["extracted_rules", "never_rules", "conflicts", "not_promoted", "summary"],
    "additionalProperties": False,
}

PROMPT = """Distil this corpus of historical flyer prompts into a permanent design system.

You are NOT summarising the prompts. You are extracting the knowledge inside
them and discarding the wording.

## Corpus

SUCCESSFUL ({n_success} prompt(s)) - these produced flyers the operator liked:
{successful}

UNSUCCESSFUL ({n_fail} prompt(s)) - these produced flyers the operator rejected:
{unsuccessful}

## Rules already in the system (do not re-extract these)

{existing}

## Your task

1. **Deduplicate.** If a concept appears ten times, emit ONE rule with
   `evidence_count: 10`. Repeated instructions are the strongest signal that
   something belongs in the permanent system.

2. **Classify scope.** `global` applies to nearly every flyer. `campaign` applies
   only to certain campaigns - list them in `applies_to`. `client` is specific to
   this contractor. `reference-influenced` came from analysing one reference and
   is provisional.

3. **Classify strength.** `hard` = follow essentially every time.
   `soft` = follow by default, may be broken when composition benefits.
   `optional` = a technique for appropriate campaigns, never universal.
   Be conservative: promote to `hard` only what the corpus shows repeatedly and
   consistently.

4. **Analyse failures.** For each unsuccessful example work out what actually
   went wrong - vague instruction, over-restriction, conflicting instructions,
   encouraged generic design, caused excessive text, caused repetitive layout,
   caused wrong architecture, caused poor typography or hierarchy, misused
   manufacturer branding, produced an unrealistic property, over-designed.
   Turn each into a `never_rules` entry.

5. **Surface conflicts.** Never silently pick a winner. Report the conflict, your
   resolution and your reason. Prefer: campaign-specific over generic; newer and
   more specific over older and vaguer; validated successful results over stated
   theory; client-specific over generic. Set `needs_operator_decision` when the
   evidence genuinely does not settle it.

6. **Refuse to over-promote.** Anything that clearly only made sense for one
   particular flyer goes in `not_promoted` with a reason. This list is as
   valuable as the rules.

Do not invent a preference the corpus does not support.
"""


def _read_corpus(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    documents = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {".md", ".txt"} or path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        documents.append({"file": path.name, "text": text[:MAX_PROMPT_CHARS]})
    return documents


def distill(claude: ClaudeClient | None = None) -> dict:
    """Analyse the corpus and return the proposal payload."""
    from ..design_system import principles

    settings = get_settings()
    root = settings.paths.design_system / "historical-prompts"
    successful = _read_corpus(root / "successful")
    unsuccessful = _read_corpus(root / "unsuccessful")

    if not successful and not unsuccessful:
        raise AIError(
            "No historical prompts found. Add .md or .txt files to "
            "design-system/historical-prompts/successful/ and /unsuccessful/ first."
        )

    claude = claude or get_claude()
    if not claude.enabled:
        raise AIError("Distillation requires Claude. Set ANTHROPIC_API_KEY.")

    existing = principles()
    existing_rules = [
        r["rule"]
        for section in existing.values()
        if isinstance(section, list)
        for r in section
        if isinstance(r, dict) and "rule" in r
    ]

    log.info(
        "Distilling %d successful and %d unsuccessful prompt(s)",
        len(successful),
        len(unsuccessful),
    )

    payload = claude.structured(
        system=system_prompt("distiller"),
        prompt=PROMPT.format(
            n_success=len(successful),
            n_fail=len(unsuccessful),
            successful=compact_json(successful, limit=60000) or "none supplied",
            unsuccessful=compact_json(unsuccessful, limit=40000) or "none supplied",
            existing=compact_json(existing_rules, limit=8000),
        ),
        tool_name="submit_design_system_proposal",
        tool_description="Submit the distilled design-system proposal for operator review.",
        schema=DISTILL_SCHEMA,
        temperature=0.3,
        max_tokens=8000,
    )
    payload["corpus"] = {
        "successful": [d["file"] for d in successful],
        "unsuccessful": [d["file"] for d in unsuccessful],
    }
    return payload


def write_proposal(payload: dict, when: date | None = None) -> Path:
    """Write a reviewable Markdown + JSON proposal. Applies nothing."""
    import json

    settings = get_settings()
    when = when or date.today()
    out_dir = settings.paths.design_system / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{when.isoformat()}-distillation"
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    corpus = payload.get("corpus", {})
    lines = [
        f"# Design-system proposal — {when.isoformat()}",
        "",
        "> Nothing here has been applied. Review, then merge what you agree with into",
        "> `design-system/principles/principles.json` and",
        "> `design-system/failures/failed-patterns.json`.",
        "",
        f"**Corpus:** {len(corpus.get('successful', []))} successful, "
        f"{len(corpus.get('unsuccessful', []))} unsuccessful",
        "",
        "## Summary",
        "",
        payload.get("summary", ""),
        "",
    ]

    rules = payload.get("extracted_rules", [])
    if rules:
        lines += [
            "## Extracted rules",
            "",
            "| Class | Scope | Section | Evidence | Rule |",
            "|-------|-------|---------|----------|------|",
        ]
        for rule in sorted(rules, key=lambda r: (-r.get("evidence_count", 0), r["id"])):
            lines.append(
                f"| `{rule['class']}` | {rule['scope']} | {rule['section']} | "
                f"{rule.get('evidence_count', 0)} | {rule['rule']} |"
            )
        lines.append("")

    never = payload.get("never_rules", [])
    if never:
        lines += ["## Proposed NEVER rules", ""]
        for item in never:
            lines.append(f"- **{item['category']}** — {item['rule']}")
            if item.get("observed_failure"):
                lines.append(f"  - observed: {item['observed_failure']}")
        lines.append("")

    conflicts = payload.get("conflicts", [])
    if conflicts:
        lines += ["## Conflicts", ""]
        for index, conflict in enumerate(conflicts, start=1):
            flag = " **NEEDS YOUR CALL**" if conflict.get("needs_operator_decision") else ""
            lines += [
                f"### {index}. {conflict['description']}{flag}",
                "",
                f"- A: {conflict['position_a']}",
                f"- B: {conflict['position_b']}",
                f"- **Resolution:** {conflict['resolution']}",
                f"- Reason: {conflict['reason']}",
                "",
            ]

    repetition = payload.get("repetition_report", [])
    if repetition:
        lines += [
            "## Repetition collapsed",
            "",
            "| Concept | Times repeated | Collapsed into |",
            "|---------|----------------|----------------|",
        ]
        for item in repetition:
            lines.append(
                f"| {item['concept']} | {item['times_repeated']} | {item['collapsed_into']} |"
            )
        lines.append("")

    not_promoted = payload.get("not_promoted", [])
    if not_promoted:
        lines += ["## Deliberately NOT made permanent", ""]
        for item in not_promoted:
            lines.append(f"- {item['instruction']}\n  - {item['why_not']}")
        lines.append("")

    md_path = out_dir / f"{stem}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Proposal written to %s", md_path)
    return md_path
