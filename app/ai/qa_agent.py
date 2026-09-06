"""Vision-based quality control.

Deterministic checks (dimensions, file integrity, contrast, overflow, contact
details) live in ``app.pipeline.validate``. This module adds the judgement calls
a machine cannot make: does the flyer actually read, and does it sell?

It is optional - when Claude is unavailable the deterministic result stands.
"""

from __future__ import annotations

from pathlib import Path

from ..logging_setup import get_logger
from ..models import Client, FlyerSpecification, QAIssue, QAResult, Severity
from .claude_client import ClaudeClient, compact_json, get_claude
from .skill import system_prompt

log = get_logger(__name__)

QA_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "check": {
                        "type": "string",
                        "enum": [
                            "headline_readability",
                            "cta_readability",
                            "text_clipping",
                            "logo_clipping",
                            "margins",
                            "overlap",
                            "image_suitability",
                            "contrast",
                            "campaign_relevance",
                            "brand_accuracy",
                            "text_volume",
                            "visual_quality",
                        ],
                    },
                    "severity": {"type": "string", "enum": ["error", "warning"]},
                    "message": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["check", "severity", "message"],
                "additionalProperties": False,
            },
        },
        "one_line_verdict": {"type": "string"},
    },
    "required": ["passed", "score", "issues"],
    "additionalProperties": False,
}

PROMPT = """Review this rendered flyer as an art director signing off client work.

INTENDED SPECIFICATION:
{spec}

CLIENT CONTACT DETAILS (must appear exactly as written, if shown at all):
{contact}

Check, in order of importance:

1. Readability at thumbnail size. Imagine this 180px wide in a feed. Is the
   headline still legible? If not, that is an `error`.
2. Contrast. Any text sitting on a photo area too bright or too busy for it.
3. Clipping and overlap. Text or logo running off an edge, colliding with
   another element, or crowding the margins.
4. Text volume. More than roughly 25 words on the flyer is too many.
5. Campaign relevance. Does the imagery match the service being advertised?
   A kitchen photo on a roofing flyer is an `error`.
6. Brand accuracy. Company name and contact details rendered correctly.
7. Visual quality. Does this look like professional contractor advertising, or
   like a template? Cheap, cluttered or generic reads as a `warning`.

Mark `passed` false only when at least one `error` exists. Be exacting but do
not invent problems - a plain, clean flyer that reads well is a pass.
"""


def vision_qa(
    image_path: Path,
    spec: FlyerSpecification,
    client: Client,
    claude: ClaudeClient | None = None,
) -> QAResult | None:
    """Return a QA result, or ``None`` when the vision pass could not run."""
    claude = claude or get_claude()
    if not claude.enabled:
        return None

    try:
        payload = claude.vision(
            images=[image_path],
            system=system_prompt("qa", client.id),
            prompt=PROMPT.format(
                spec=compact_json(
                    {
                        "campaign": spec.campaign_id,
                        "service": spec.service,
                        "layout": spec.layout.name,
                        "style": spec.style,
                        "text": spec.text.model_dump(),
                        "canvas": spec.canvas.model_dump(),
                    }
                ),
                contact=compact_json(client.contact.model_dump()),
            ),
            tool_name="submit_qa_review",
            tool_description="Submit the art-director review of a rendered flyer.",
            schema=QA_SCHEMA,
            max_tokens=2000,
        )
    except Exception as exc:
        log.warning("Vision QA unavailable (%s); deterministic checks stand", exc)
        return None

    issues = [
        QAIssue(
            check=item["check"],
            severity=Severity(item["severity"]),
            message=item["message"],
            detail=item.get("detail", ""),
        )
        for item in payload.get("issues", [])
    ]
    errors = [i for i in issues if i.severity is Severity.ERROR]
    verdict = payload.get("one_line_verdict", "")
    if verdict:
        log.info("Vision QA: %s", verdict)

    return QAResult(
        passed=bool(payload.get("passed", True)) and not errors,
        score=int(payload.get("score", 100)),
        issues=errors,
        warnings=[i for i in issues if i.severity is Severity.WARNING],
        checked_by="claude-vision",
    )
