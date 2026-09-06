"""Client profile models."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class Contact(BaseModel):
    phone: str = ""
    website: str = ""
    email: str = ""
    address: str = ""

    @property
    def has_any(self) -> bool:
        return any((self.phone, self.website, self.email))


class Brand(BaseModel):
    primary_colors: list[str] = Field(default_factory=lambda: ["#0F1B2B"])
    secondary_colors: list[str] = Field(default_factory=lambda: ["#E8B03A"])
    neutral_colors: list[str] = Field(default_factory=lambda: ["#FFFFFF", "#111111"])
    fonts: dict[str, str] = Field(
        default_factory=lambda: {"headline": "Anton", "body": "Inter"},
        description="Logical role -> font family name. Resolved by rendering.typography.",
    )
    logo_path: str = ""
    logo_dark_path: str = ""

    @field_validator("primary_colors", "secondary_colors", "neutral_colors")
    @classmethod
    def _validate_colors(cls, values: list[str]) -> list[str]:
        for value in values:
            if not HEX_COLOR.match(value):
                raise ValueError(f"{value!r} is not a #RGB or #RRGGBB hex colour")
        return values

    @property
    def primary(self) -> str:
        return self.primary_colors[0] if self.primary_colors else "#0F1B2B"

    @property
    def accent(self) -> str:
        return self.secondary_colors[0] if self.secondary_colors else "#E8B03A"


class Product(BaseModel):
    """A manufacturer product the client installs.

    Manufacturer brands are always subordinate to the client's own identity:
    they are material options, not the advertiser.
    """

    id: str
    name: str = Field(description="Full product name including the manufacturer mark")
    manufacturer: str = ""
    category: str = Field(default="general", description="Service this product belongs to")
    benefits: list[str] = Field(
        default_factory=list,
        description="Verified product benefits. The only product claims copy may state.",
    )
    show_manufacturer_mark: bool = Field(
        default=True,
        description="Whether the manufacturer name may appear in copy at all",
    )


class Offer(BaseModel):
    """An offer the client has authorised. Copy may not invent offers."""

    id: str
    text: str
    fine_print: str = ""
    expires: str = ""
    services: list[str] = Field(default_factory=list)


class DriveConfig(BaseModel):
    root_folder_id: str = ""
    subfolder_name: str = ""


class Client(BaseModel):
    id: str
    company_name: str
    industry: str = "residential construction"
    location: str = ""
    service_area: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    target_audience: str = "Residential homeowners"
    tone: list[str] = Field(default_factory=lambda: ["professional", "trustworthy"])
    primary_goal: Literal["lead_generation", "brand", "phone_call", "trust"] = "lead_generation"

    brand: Brand = Field(default_factory=Brand)
    contact: Contact = Field(default_factory=Contact)
    drive: DriveConfig = Field(default_factory=DriveConfig)

    offers: list[Offer] = Field(default_factory=list)
    products: list[Product] = Field(
        default_factory=list,
        description="Manufacturer products the client installs. Subordinate to the client brand.",
    )
    proof_points: list[str] = Field(
        default_factory=list,
        description="Verified claims only - licence numbers, years in business, warranty terms. "
        "Copy may cite these verbatim and may cite nothing else.",
    )
    forbidden_claims: list[str] = Field(default_factory=list)
    preferred_reference_styles: list[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", value):
            raise ValueError(f"client id {value!r} must be a lowercase slug (a-z, 0-9, '-')")
        return value

    def products_for(self, service: str) -> list[Product]:
        return [p for p in self.products if p.category in (service, "general")]

    @property
    def service_slugs(self) -> list[str]:
        return [s.strip().lower().replace(" ", "-") for s in self.services]
