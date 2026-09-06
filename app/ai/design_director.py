"""Turn a plan + copy + chosen assets into a FlyerSpecification.

The design director makes *art-direction* decisions only - overlay, crop,
alignment, accent colour, logo position. It cannot invent copy or assets: those
are passed in and copied through verbatim, so a hallucinated asset id can never
reach the renderer.
"""

from __future__ import annotations

from typing import Any

from ..logging_setup import get_logger
from ..models import (
    Asset,
    CanvasSpec,
    Client,
    FlyerCopy,
    FlyerSpecification,
    ImageSpec,
    LayoutSpec,
    PlannedFlyer,
    ReferenceImage,
)
from .claude_client import ClaudeClient, compact_json, get_claude
from .skill import system_prompt

log = get_logger(__name__)

DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "style": {
            "type": "string",
            "enum": [
                "premium-modern",
                "bold-promotional",
                "clean-minimal",
                "corporate-trust",
                "urgent-emergency",
                "warm-residential",
            ],
        },
        "overlay": {
            "type": "string",
            "enum": [
                "none",
                "dark_gradient",
                "dark_flat",
                "brand_gradient",
                "light_flat",
                "vignette",
            ],
        },
        "overlay_strength": {"type": "number", "minimum": 0.2, "maximum": 0.92},
        "crop": {"type": "string", "enum": ["center", "top", "bottom", "left", "right", "focal"]},
        "grayscale": {"type": "boolean"},
        "text_align": {"type": "string", "enum": ["left", "center"]},
        "type_pairing": {
            "type": "string",
            "enum": [
                "condensed-editorial",
                "impact-promotional",
                "grotesque-corporate",
                "serif-editorial",
                "condensed-industrial",
            ],
            "description": "The type system. Vary this across flyers - a week of identical typography is a failure.",
        },
        "accent_shape": {"type": "boolean"},
        "logo_position": {
            "type": "string",
            "enum": ["top-left", "top-right", "bottom-left", "bottom-right", "none"],
        },
        "show_contact_bar": {"type": "boolean"},
        "accent_color": {
            "type": "string",
            "pattern": "^#[0-9a-fA-F]{6}$",
            "description": "Must be one of the client's brand colours.",
        },
        "designer_notes": {"type": "string"},
    },
    "required": ["style", "overlay", "overlay_strength", "crop", "text_align", "logo_position"],
    "additionalProperties": False,
}

PROMPT = """Art-direct one flyer. The copy and the photograph are already chosen -
your job is the treatment.

LAYOUT: {layout}  (archetype: {archetype})
{layout_description}

THE ONE THING THIS FLYER IS ABOUT: {primary_message}

COPY (already final - do not rewrite):
{copy}

PHOTOGRAPH:
{asset}

BRAND:
{brand}

REFERENCE DESIGN DNA (inspiration only - never reproduce the reference):
{reference}

Decide the treatment. Key judgements:

1. Overlay strength. The headline sits over the image in `hero-full`,
   `offer-badge` and `split-diagonal`. A bright or busy photo needs 0.6-0.85.
   A calm dark photo needs 0.35-0.5. Under-darkening is the single most common
   failure - when unsure, go darker.
2. Crop. Use `focal` unless the layout needs the sky (`top`) or the roofline
   (`bottom`).
3. Accent colour must come from the brand palette listed above.
4. Logo position must not collide with the copy stack for this layout.
5. Vary the treatment from recent flyers - every flyer looking identical is a
   failure even when each one is individually fine.
"""


def direct_design(
    client: Client,
    planned: PlannedFlyer,
    copy: FlyerCopy,
    asset: Asset | None,
    secondary_asset: Asset | None,
    reference: ReferenceImage | None,
    layout_description: str,
    canvas: CanvasSpec,
    flyer_id: str,
    claude: ClaudeClient | None = None,
) -> FlyerSpecification:
    claude = claude or get_claude()
    brand_colors = [
        *client.brand.primary_colors,
        *client.brand.secondary_colors,
    ]

    payload: dict = {}
    if claude.enabled:
        try:
            payload = claude.structured(
                system=system_prompt("designer", client.id),
                prompt=PROMPT.format(
                    layout=planned.layout,
                    archetype=planned.archetype or "not specified",
                    primary_message=planned.primary_message or "not specified",
                    layout_description=layout_description,
                    copy=compact_json(copy.model_dump()),
                    asset=compact_json(
                        {
                            "asset_id": asset.id,
                            "service": asset.service,
                            "mean_luminance": asset.mean_luminance,
                            "contrast": asset.contrast,
                            "clear_regions": asset.clear_regions,
                            "orientation": "portrait" if asset.is_portrait else "landscape",
                        }
                    )
                    if asset
                    else "none - the renderer will generate a brand-coloured background",
                    brand=compact_json(
                        {
                            "primary_colors": client.brand.primary_colors,
                            "secondary_colors": client.brand.secondary_colors,
                            "has_logo": bool(client.brand.logo_path),
                            "tone": client.tone,
                        }
                    ),
                    reference=compact_json(
                        {
                            "style": reference.style,
                            "image_treatment": reference.image_treatment,
                            "text_density": reference.text_density,
                            "visual_weight": reference.visual_weight,
                            "cta_position": reference.cta_position,
                            "composition_notes": reference.composition_notes,
                            "negative_space": reference.negative_space,
                        }
                    )
                    if reference
                    else "none available - use the client's brand and the layout defaults",
                ),
                tool_name="submit_design_specification",
                tool_description="Submit art-direction decisions for one flyer.",
                schema=DESIGN_SCHEMA,
                temperature=0.8,
                max_tokens=1200,
            )
        except Exception as exc:
            log.warning("Design director falling back to layout defaults: %s", exc)
            payload = {}

    defaults = _defaults(planned.layout, asset)
    merged = {**defaults, **{k: v for k, v in payload.items() if v is not None}}

    accent = merged.get("accent_color") or client.brand.accent
    if accent not in brand_colors:
        accent = client.brand.accent

    palette = {
        "primary": client.brand.primary,
        "accent": accent,
        "ink": _pick_ink(client),
        "paper": "#FFFFFF",
        "on_image": "#FFFFFF",
    }

    return FlyerSpecification(
        id=flyer_id,
        client_id=client.id,
        campaign_id=planned.campaign_id,
        service=planned.service,
        style=merged.get("style", "premium-modern"),
        canvas=canvas,
        layout=LayoutSpec(
            name=planned.layout,
            text_align=merged.get("text_align", "left"),
            type_pairing=_resolve_pairing(merged),
            accent_shape=bool(merged.get("accent_shape", True)),
            logo_position=merged.get("logo_position", "top-left"),
            show_contact_bar=bool(merged.get("show_contact_bar", True)),
        ),
        image=ImageSpec(
            asset_id=asset.id if asset else None,
            secondary_asset_id=secondary_asset.id if secondary_asset else None,
            crop=merged.get("crop", "focal"),
            overlay=merged.get("overlay", "dark_gradient"),
            overlay_strength=float(merged.get("overlay_strength", 0.58)),
            grayscale=bool(merged.get("grayscale", False)),
        ),
        text=copy,
        palette=palette,
        reference_ids=[reference.id] if reference else [],
        designer_notes=merged.get("designer_notes", ""),
    )


def _resolve_pairing(merged: dict) -> str:
    """Validate the chosen type pairing against what is actually configured."""
    from ..rendering.typography import list_pairings, pairings_for_style

    available = list_pairings()
    chosen = merged.get("type_pairing")
    if chosen in available:
        return chosen
    suited = [
        p for p in pairings_for_style(merged.get("style", "premium-modern")) if p in available
    ]
    return suited[0] if suited else (available[0] if available else "condensed-editorial")


# Layouts that draw their own footer must not also reserve contact-bar height.
NO_CONTACT_BAR = {"hero-editorial"}


def _defaults(layout: str, asset: Asset | None) -> dict[str, Any]:
    """Sensible art direction per layout, used when Claude is off or fails."""
    base: dict[str, Any] = {
        "hero-full": {
            "style": "premium-modern",
            "type_pairing": "serif-editorial",
            "overlay": "dark_gradient",
            "overlay_strength": 0.62,
            "crop": "focal",
            "text_align": "left",
            "logo_position": "top-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
        "banner-lower-third": {
            "style": "corporate-trust",
            "type_pairing": "condensed-editorial",
            "overlay": "none",
            "overlay_strength": 0.25,
            "crop": "focal",
            "text_align": "left",
            "logo_position": "top-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
        "split-diagonal": {
            "style": "bold-promotional",
            "type_pairing": "impact-promotional",
            "overlay": "dark_flat",
            "overlay_strength": 0.35,
            "crop": "top",
            "text_align": "left",
            "logo_position": "bottom-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
        "offer-badge": {
            "style": "urgent-emergency",
            "type_pairing": "impact-promotional",
            "overlay": "dark_flat",
            "overlay_strength": 0.72,
            "crop": "focal",
            "text_align": "center",
            "logo_position": "top-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
        "before-after": {
            "style": "warm-residential",
            "type_pairing": "condensed-editorial",
            "overlay": "none",
            "overlay_strength": 0.2,
            "crop": "center",
            "text_align": "center",
            "logo_position": "top-left",
            "accent_shape": False,
            "show_contact_bar": True,
        },
        "stat-stack": {
            "style": "clean-minimal",
            "type_pairing": "grotesque-corporate",
            "overlay": "dark_gradient",
            "overlay_strength": 0.8,
            "crop": "focal",
            "text_align": "left",
            "logo_position": "top-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
    }.get(
        layout,
        {
            "style": "premium-modern",
            "overlay": "dark_gradient",
            "overlay_strength": 0.6,
            "crop": "focal",
            "text_align": "left",
            "logo_position": "top-left",
            "accent_shape": True,
            "show_contact_bar": True,
        },
    )

    if layout in NO_CONTACT_BAR:
        base = {**base, "show_contact_bar": False}

    # Bright photographs need a heavier scrim than the layout default.
    if asset and asset.mean_luminance > 0.62 and base["overlay"] != "none":
        stronger = min(float(base["overlay_strength"]) + 0.15, 0.9)
        base = {**base, "overlay_strength": stronger}
    return base


def _pick_ink(client: Client) -> str:
    """A dark neutral for text on white. Prefers a brand neutral if one is dark."""
    from ..rendering.composition import relative_luminance

    for color in client.brand.neutral_colors:
        if relative_luminance(color) < 0.25:
            return color
    return "#101418"
