"""Photography / asset models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Region = Literal[
    "top",
    "bottom",
    "left",
    "right",
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
]


class SourceType(StrEnum):
    """Where an image actually came from. Never inferred from a filename."""

    CLIENT_PHOTO = "client_photo"  # a real photograph of a real client project
    CLIENT_VIDEO_FRAME = "client_frame"  # a frame extracted from real client video
    CLIENT_DRONE = "client_drone"  # real drone stills
    INTERNAL_BACKGROUND = "internal"  # approved generic company photography
    STOCK = "stock"  # licensed stock (Unsplash etc.)
    PLACEHOLDER = "placeholder"  # synthetic scaffolding. NEVER production
    GENERATED_SAMPLE = "generated"  # AI/procedurally generated. NEVER production
    UNKNOWN = "unknown"  # provenance not established. NEVER production


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    UNAPPROVED = "unapproved"
    REJECTED = "rejected"


# Only these source types may ever appear in a client-facing flyer, and only
# when they are also explicitly approved.
PRODUCTION_SOURCE_TYPES = frozenset(
    {
        SourceType.CLIENT_PHOTO,
        SourceType.CLIENT_VIDEO_FRAME,
        SourceType.CLIENT_DRONE,
        SourceType.INTERNAL_BACKGROUND,
        SourceType.STOCK,
    }
)

# Ranking for selection. Real client media beats everything.
SOURCE_RANK: dict[str, int] = {
    SourceType.CLIENT_PHOTO: 100,
    SourceType.CLIENT_DRONE: 95,
    SourceType.CLIENT_VIDEO_FRAME: 90,
    SourceType.INTERNAL_BACKGROUND: 70,
    SourceType.STOCK: 45,
    SourceType.GENERATED_SAMPLE: 5,
    SourceType.PLACEHOLDER: 0,
    SourceType.UNKNOWN: 0,
}


class Provenance(BaseModel):
    """Verifiable origin of an image. The anti-contamination record.

    ``production_eligible`` is *derived*, never hand-set, so a placeholder
    cannot be promoted into production by editing one field.
    """

    source_type: SourceType = SourceType.UNKNOWN
    approval_status: ApprovalStatus = ApprovalStatus.UNAPPROVED

    origin_path: str = Field(default="", description="Where it was ingested from")
    project: str = Field(default="", description="Project slug, e.g. 'bergenfield'")
    address_label: str = Field(default="", description="Human label, e.g. 'Bergenfield'")
    stage: Literal["", "before", "during", "after", "neutral"] = Field(
        default="",
        description=(
            "What state the work is in. 'before' is the old/damaged condition, "
            "'during' is mid-installation, 'after' is finished work, 'neutral' is "
            "a property with no visible work state. Empty means unclassified, "
            "which bars the image from any message that implies finished work."
        ),
    )

    hold_reason: str = Field(
        default="",
        description=(
            "Why this photograph must not be published, in plain words. Set it and "
            "the asset stops being production-eligible no matter how it is approved "
            "elsewhere. Written for the things no automated check can see - a worker "
            "on a roof edge without fall protection, a recognisable face, a "
            "neighbour's property, a customer's licence plate."
        ),
    )

    captured_at: str = ""
    camera: str = Field(default="", description="EXIF Make/Model when present")
    source_video: str = Field(default="", description="For extracted frames")
    frame_time_s: float | None = None

    ingested_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    verified_by: str = Field(default="", description="How provenance was established")
    notes: str = ""

    @property
    def production_eligible(self) -> bool:
        """Derived. A placeholder can never satisfy this."""
        return (
            self.source_type in PRODUCTION_SOURCE_TYPES
            and self.approval_status is ApprovalStatus.APPROVED
            and not self.hold_reason
        )

    @property
    def rank(self) -> int:
        return SOURCE_RANK.get(self.source_type, 0)

    @property
    def is_synthetic(self) -> bool:
        return self.source_type in (SourceType.PLACEHOLDER, SourceType.GENERATED_SAMPLE)


class FocalPoint(BaseModel):
    """Normalised 0..1 focal point used to bias cropping."""

    x: float = 0.5
    y: float = 0.5


class Asset(BaseModel):
    id: str
    path: str = Field(description="Repo-relative path")
    client_id: str | None = Field(
        default=None, description="None for the shared library, else the owning client"
    )
    service: str = "general"
    tags: list[str] = Field(default_factory=list)

    width: int = 0
    height: int = 0
    sha256: str = ""

    focal: FocalPoint = Field(default_factory=FocalPoint)
    clear_regions: list[str] = Field(
        default_factory=list,
        description="Regions with enough negative space to carry text",
    )
    mean_luminance: float = 0.5
    contrast: float = 0.5
    is_portrait: bool = False

    provenance: Provenance = Field(default_factory=Provenance)
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Composite suitability score from media ingestion",
    )

    times_used: int = 0
    last_used: str = ""
    added_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    @property
    def is_client_owned(self) -> bool:
        return self.client_id is not None

    @property
    def production_eligible(self) -> bool:
        """The single gate every production selection must pass."""
        return self.provenance.production_eligible

    @property
    def is_synthetic(self) -> bool:
        return self.provenance.is_synthetic

    @model_validator(mode="after")
    def _synthetic_can_never_be_approved(self) -> Asset:
        """Structural guarantee: synthetic media cannot be marked approved.

        This is deliberately enforced in the model rather than in the selector,
        so no future code path can approve a placeholder by mistake.
        """
        if (
            self.provenance.is_synthetic
            and self.provenance.approval_status is ApprovalStatus.APPROVED
        ):
            self.provenance.approval_status = ApprovalStatus.UNAPPROVED
        return self


class AssetIndex(BaseModel):
    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    assets: list[Asset] = Field(default_factory=list)

    def by_id(self, asset_id: str) -> Asset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    def upsert(self, asset: Asset) -> None:
        for index, existing in enumerate(self.assets):
            if existing.id == asset.id:
                merged = asset.model_copy(
                    update={
                        "times_used": existing.times_used,
                        "last_used": existing.last_used,
                        "added_at": existing.added_at,
                    }
                )
                self.assets[index] = merged
                break
        else:
            self.assets.append(asset)
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
