"""Campaign catalogue and daily plan models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Campaign(BaseModel):
    id: str
    service: str
    name: str
    angle: str
    objective: str = "lead_generation"
    seasons: list[str] = Field(default_factory=lambda: ["all"])
    preferred_layouts: list[str] = Field(default_factory=list)

    def in_season(self, season: str) -> bool:
        return "all" in self.seasons or season in self.seasons


class CampaignCatalog(BaseModel):
    version: int = 1
    campaigns: list[Campaign] = Field(default_factory=list)
    angles: dict[str, str] = Field(default_factory=dict)

    def by_id(self, campaign_id: str) -> Campaign | None:
        return next((c for c in self.campaigns if c.id == campaign_id), None)

    def for_services(self, services: list[str]) -> list[Campaign]:
        """Campaigns whose service the client actually offers ('general' always applies)."""
        wanted = {s.strip().lower() for s in services}
        return [c for c in self.campaigns if c.service == "general" or c.service in wanted]


class Brief(BaseModel):
    """The only thing an operator has to supply per flyer.

    Everything else - brand, palette, typography, photography rules, density,
    format, negative rules - comes from the Skill and the client profile. This
    is the prompt-minimisation contract.
    """

    message: str = Field(default="", description="The one thing this flyer is about")
    archetype: str = Field(default="", description="Composition archetype id, optional")
    product_id: str | None = Field(default=None, description="Manufacturer product to feature")
    cta: str = Field(default="", description="Override the call to action")
    reference_id: str | None = Field(default=None, description="Force a specific reference")

    @property
    def is_empty(self) -> bool:
        return not any((self.message, self.archetype, self.product_id, self.cta, self.reference_id))


class PlannedFlyer(BaseModel):
    """One flyer's strategic brief, produced by the campaign planner."""

    slot: int = Field(ge=1, description="1-based position in today's batch")
    campaign_id: str
    service: str
    angle: str
    layout: str
    rationale: str = ""
    offer_id: str | None = None
    primary_message: str = Field(
        default="",
        description="Operator-supplied angle for this specific flyer, e.g. 'built-in insulation'",
    )
    product_id: str | None = Field(
        default=None, description="Manufacturer product this flyer features, if any"
    )
    archetype: str = Field(
        default="", description="Composition archetype id from the design system"
    )


class CampaignPlan(BaseModel):
    client_id: str
    date: str
    season: str
    flyers: list[PlannedFlyer]
    strategy_note: str = ""
