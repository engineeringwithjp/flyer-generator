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
    support: str = Field(default="", max_length=110)
    bullets: list[str] = Field(default_factory=list, max_length=3)
    cta: str = Field(min_length=3, max_length=32)
    offer_badge: str = Field(default="", max_length=26)
    disclaimer: str = Field(default="", max_length=120)

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
            "asset_ids": [r.spec.image.asset_id for r in self.results if r.spec.image.asset_id],
            "errors": self.errors,
        }
