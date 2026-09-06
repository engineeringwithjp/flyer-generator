"""Design-reference models.

A reference is *design DNA*, never artwork to reproduce. The metadata below is
deliberately abstract - layout family, densities, treatments - so that nothing
downstream can copy a third-party flyer even if it wanted to.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ReferenceStatus(StrEnum):
    APPROVED = "approved"
    EXPERIMENTAL = "experimental"
    REJECTED = "rejected"
    INBOX = "inbox"


class ReferenceImage(BaseModel):
    id: str
    filename: str = Field(description="Original filename as supplied by the user")
    path: str = Field(description="Repo-relative path to the stored image")
    status: ReferenceStatus = ReferenceStatus.EXPERIMENTAL

    category: str = "general"
    style: str = "modern"
    layout: str = "hero-background"
    text_density: str = "medium"
    visual_weight: str = "balanced"
    cta_position: str = "bottom-center"
    image_treatment: str = "none"
    typography: str = ""
    color_characteristics: list[str] = Field(default_factory=list)
    dominant_colors: list[str] = Field(default_factory=list)
    composition_notes: str = ""
    negative_space: str = ""
    recommended_campaigns: list[str] = Field(default_factory=list)
    suggested_layouts: list[str] = Field(default_factory=list)
    description: str = ""

    sha256: str = ""
    width: int = 0
    height: int = 0
    analyzed_by: str = ""
    added_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # Feedback loop
    times_used: int = 0
    approvals: int = 0
    rejections: int = 0

    @property
    def performance(self) -> float:
        """0..1 approval rate; unused references sit at a neutral 0.5."""
        total = self.approvals + self.rejections
        return 0.5 if total == 0 else self.approvals / total


class ReferenceIndex(BaseModel):
    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    references: list[ReferenceImage] = Field(default_factory=list)

    def by_id(self, ref_id: str) -> ReferenceImage | None:
        return next((r for r in self.references if r.id == ref_id), None)

    def usable(self) -> list[ReferenceImage]:
        """Everything except rejected and un-analysed inbox items."""
        return [
            r
            for r in self.references
            if r.status in (ReferenceStatus.APPROVED, ReferenceStatus.EXPERIMENTAL)
        ]

    def next_id(self) -> str:
        highest = 0
        for ref in self.references:
            if ref.id.startswith("ref_"):
                try:
                    highest = max(highest, int(ref.id.removeprefix("ref_")))
                except ValueError:
                    continue
        return f"ref_{highest + 1:06d}"

    def upsert(self, reference: ReferenceImage) -> None:
        for index, existing in enumerate(self.references):
            if existing.id == reference.id:
                self.references[index] = reference
                break
        else:
            self.references.append(reference)
        self.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
