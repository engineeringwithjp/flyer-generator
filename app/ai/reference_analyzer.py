"""Claude vision analysis of a reference flyer.

Output is deliberately abstract design metadata. The prompt explicitly forbids
transcribing the reference's copy, branding or contact details, so nothing
downstream can reproduce someone else's advert.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import AIError
from ..logging_setup import get_logger
from .claude_client import ClaudeClient, get_claude
from .skill import system_prompt

log = get_logger(__name__)

CATEGORIES = [
    "roofing",
    "siding",
    "gutters",
    "windows",
    "hvac",
    "plumbing",
    "electrical",
    "remodeling",
    "general",
]
STYLES = [
    "premium-modern",
    "bold-promotional",
    "clean-minimal",
    "corporate-trust",
    "urgent-emergency",
    "warm-residential",
    "industrial",
]
LAYOUTS = [
    "hero-background",
    "lower-third-band",
    "diagonal-split",
    "centered-badge",
    "before-after",
    "typographic-stack",
    "grid-collage",
]

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "style": {"type": "string", "enum": STYLES},
        "layout": {"type": "string", "enum": LAYOUTS},
        "text_density": {"type": "string", "enum": ["low", "medium", "high"]},
        "visual_weight": {
            "type": "string",
            "enum": ["image-heavy", "balanced", "type-heavy"],
        },
        "cta_position": {
            "type": "string",
            "enum": [
                "top-left",
                "top-right",
                "top-center",
                "center",
                "bottom-left",
                "bottom-right",
                "bottom-center",
                "none",
            ],
        },
        "image_treatment": {
            "type": "string",
            "enum": [
                "none",
                "dark-gradient",
                "dark-flat",
                "brand-gradient",
                "duotone",
                "vignette",
                "cutout",
                "light-wash",
            ],
        },
        "typography": {
            "type": "string",
            "description": "Short description of the type system, e.g. 'condensed heavy sans headline over light sans body'",
        },
        "color_characteristics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "e.g. 'high contrast', 'single accent', 'dark neutral base'",
        },
        "dominant_colors": {
            "type": "array",
            "items": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
            "description": "Up to 4 hex colours describing the palette relationships",
        },
        "composition_notes": {
            "type": "string",
            "description": "How the eye moves through the design. No transcription of the copy.",
        },
        "negative_space": {
            "type": "string",
            "description": "Where the design leaves room to breathe",
        },
        "recommended_campaigns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Campaign ids from the catalogue this design language suits",
        },
        "suggested_layouts": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "hero-full",
                    "banner-lower-third",
                    "split-diagonal",
                    "offer-badge",
                    "before-after",
                    "stat-stack",
                ],
            },
            "description": "Which of OUR renderer layouts best express this design language",
        },
        "description": {
            "type": "string",
            "description": "One or two sentences describing the design approach in the abstract",
        },
    },
    "required": [
        "category",
        "style",
        "layout",
        "text_density",
        "visual_weight",
        "cta_position",
        "image_treatment",
        "description",
        "suggested_layouts",
    ],
    "additionalProperties": False,
}

PROMPT = """Analyse the attached marketing flyer as a *design reference*.

You are extracting reusable design DNA for an original flyer generator. You are
NOT cataloguing this advert for reproduction.

Describe:
- composition and how the eye moves through it
- visual hierarchy and typographic weight relationships
- spacing, margins and negative space
- image treatment and overlays
- colour relationships (report hex approximations of the palette, not brand identity)
- CTA placement and prominence
- overall visual density

Do NOT record, quote, paraphrase or infer:
- the advertiser's company name, logo, slogan, phone number, website or address
- the headline or body copy wording
- any offer, price or discount shown
- anything that would let someone recreate this specific advert

Then map the design onto our own renderer by choosing `suggested_layouts` from
the allowed list, and name the campaign ids this design language would suit.

Available campaign ids:
{campaign_ids}
"""


def analyze_reference(
    image_path: Path,
    campaign_ids: list[str],
    claude: ClaudeClient | None = None,
) -> dict:
    """Return validated design metadata for one reference image."""
    claude = claude or get_claude()
    if not claude.enabled:
        raise AIError(
            "Reference analysis requires Claude. Set ANTHROPIC_API_KEY (and unset FLYER_OFFLINE)."
        )

    log.info("Analysing reference image %s", image_path.name)
    result = claude.vision(
        images=[image_path],
        system=system_prompt("reference"),
        prompt=PROMPT.format(campaign_ids=", ".join(campaign_ids)),
        tool_name="record_reference_metadata",
        tool_description="Record abstract design metadata for a reference flyer.",
        schema=ANALYSIS_SCHEMA,
        max_tokens=2048,
    )
    result.setdefault("recommended_campaigns", [])
    result.setdefault("dominant_colors", [])
    result.setdefault("color_characteristics", [])
    return result
