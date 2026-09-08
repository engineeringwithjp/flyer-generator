"""Flyer specification, result and run models.

``FlyerSpecification`` is the single contract between Claude and the renderer.
Claude produces it; the renderer consumes it and invents nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Overlay = Literal["none", "dark_gradient", "dark_flat", "brand_gradient", "light_flat", "vignette"]
Crop = Literal["center", "top", "bottom", "left", "right", "focal"]


class CanvasSpec(BaseModel):
    width: int = 1080
    height: int = 1350

    @property
    def aspect(self) -> float:
        return self.width / self.height


class LayoutSpec(BaseModel):
    name: str = Field(description="Layout id from config/layouts.json")
    type_pairing: str = Field(
        default="condensed-editorial",
        description="Type system id from config/typography.json",
    )
    text_align: Literal["left", "center"] = "left"
    accent_shape: bool = True
    logo_position: Literal["top-left", "top-right", "bottom-left", "bottom-right", "none"] = (
        "top-left"
    )
    show_contact_bar: bool = True


class ImageSpec(BaseModel):
    asset_id: str | None = None
    secondary_asset_id: str | None = Field(
        default=None, description="Second panel for before-after layouts"
    )
    pair_confirmed: bool = Field(
        default=False,
        description=(
            "A person has confirmed the before and after photographs are the same "
            "property. Nothing can establish this automatically - matching project "
            "labels only prove the two files were filed together, and they have been "
            "wrong. Until this is set, before/after flyers do not ship."
        ),
    )
    crop: Crop = "focal"
    overlay: Overlay = "dark_gradient"
    overlay_strength: float = Field(default=0.55, ge=0.0, le=1.0)
    grayscale: bool = False


class FlyerCopy(BaseModel):
    """Character budgets are hard renderer limits, not suggestions."""

    eyebrow: str = Field(default="", max_length=34)
    headline: str = Field(min_length=3, max_length=54)
    accent_word: str = Field(
        default="",
        max_length=18,
        description="One word of the headline rendered in the accent colour. "
        "The single most repeated device in the operator's reference flyers. "
        "Must appear verbatim in the headline, else it is ignored.",
    )
    chips: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Short pill labels, e.g. process steps or service names. "
        "2-4 words each. Replaces bullets in editorial layouts.",
    )
    callout_number: str = Field(
        default="",
        max_length=2,
        description="Oversized numeral for a carousel card, e.g. '3'. Empty for none.",
    )
    callout_lead: str = Field(
        default="",
        max_length=30,
        description="Bold line beside the numeral, e.g. 'Look out for these'.",
    )
    callout_body: str = Field(
        default="",
        max_length=90,
        description="Smaller line under the lead, e.g. 'signs to prevent a total "
        "structural meltdown'.",
    )
    support: str = Field(default="", max_length=110)
    bullets: list[str] = Field(default_factory=list, max_length=3)
    cta: str = Field(min_length=3, max_length=32)
    offer_badge: str = Field(default="", max_length=26)
    disclaimer: str = Field(default="", max_length=120)

    # --- educational card, matching the client's approved carousel template ---
    card_title: str = Field(
        default="",
        max_length=44,
        description="Centred title on the body band, e.g. 'CRACKING & WARPING'.",
    )
    looks_like: str = Field(
        default="",
        max_length=190,
        description="What the homeowner can see. Concrete and checkable.",
    )
    harmful: str = Field(
        default="",
        max_length=210,
        description="Why it matters. Consequence, not scare tactics.",
    )

    @field_validator("headline")
    @classmethod
    def _headline_shape(cls, value: str) -> str:
        words = value.split()
        if len(words) > 8:
            raise ValueError("headline must be 8 words or fewer to survive thumbnail scaling")
        return value.strip()

    @field_validator("chips")
    @classmethod
    def _chip_length(cls, values: list[str]) -> list[str]:
        for chip in values:
            if len(chip) > 22:
                raise ValueError(f"chip {chip!r} exceeds 22 characters")
        return values

    @field_validator("bullets")
    @classmethod
    def _bullet_length(cls, values: list[str]) -> list[str]:
        for bullet in values:
            if len(bullet) > 44:
                raise ValueError(f"bullet {bullet!r} exceeds 44 characters")
        return values


class FlyerSpecification(BaseModel):
    id: str
    client_id: str
    campaign_id: str
    service: str
    style: str = "premium-modern"

    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    layout: LayoutSpec
    image: ImageSpec = Field(default_factory=ImageSpec)
    text: FlyerCopy = Field(
        description="The flyer's copy. Named `text`, not `copy`, "
        "because `copy` shadows a BaseModel method."
    )

    palette: dict[str, str] = Field(
        default_factory=dict,
        description="Resolved hex colours: primary, accent, ink, paper, on_image",
    )
    reference_ids: list[str] = Field(default_factory=list)
    designer_notes: str = ""
    tool_decision: dict = Field(
        default_factory=dict,
        description="Why each external connector was or was not used for this flyer",
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class FlyerResult(BaseModel):
    spec: FlyerSpecification
    image_path: str = ""
    metadata_path: str = ""
    width: int = 0
    height: int = 0
    bytes: int = 0
    rendered_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    qa_passed: bool = False
    qa_score: int = 0
    drive_file_id: str = ""
    drive_url: str = ""
    attempts: int = 1
    approved: bool | None = Field(
        default=None, description="Set by the human approval workflow, not by the pipeline"
    )
    rejection_reasons: list[str] = Field(default_factory=list)


class GenerationRun(BaseModel):
    run_id: str
    client_id: str
    date: str
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    finished_at: str = ""
    requested_count: int = 2
    model: str = ""
    offline: bool = False
    plan: dict = Field(default_factory=dict)
    tools_used: list[str] = Field(
        default_factory=lambda: ["claude"],
        description="Every external service this run actually called",
    )
    renderer: str = "internal"
    results: list[FlyerResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.qa_passed)

    def summary_row(self) -> dict:
        return {
            "run_id": self.run_id,
            "date": self.date,
            "client": self.client_id,
            "flyers": len(self.results),
            "passed": self.succeeded,
            "campaigns": [r.spec.campaign_id for r in self.results],
            "headlines": [r.spec.text.headline for r in self.results],
            "reference_ids": sorted({rid for r in self.results for rid in r.spec.reference_ids}),
            "layouts": [r.spec.layout.name for r in self.results],
            "type_pairings": [r.spec.layout.type_pairing for r in self.results],
            # What the client has actually seen. The planner avoids repeating
            # these, which is the only thing standing between a week of flyers
            # and seven versions of the same card.
            "delivered_layouts": [
                r.spec.layout.name for r in self.results if (r.drive_url or r.drive_file_id)
            ],
            "asset_ids": [r.spec.image.asset_id for r in self.results if r.spec.image.asset_id],
            # Only the photographs that reached the client. A flyer held in
            # staging has not been seen by anyone, so its photograph is still
            # free to use; one that shipped is not.
            "delivered_asset_ids": [
                r.spec.image.asset_id
                for r in self.results
                if r.spec.image.asset_id and (r.drive_url or r.drive_file_id)
            ],
            "errors": self.errors,
        }
