"""Data models and schemas for the Flyer Generator system."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BrandColors(BaseModel):
    primary_accent: str = "#80272B"
    secondary_accent: Optional[str] = "#9E3439"
    dark_neutral: str = "#1C1C1E"
    light_neutral: str = "#FFFFFF"
    off_white: str = "#F4F4F6"
    card_overlay: str = "rgba(28, 28, 30, 0.82)"

class ClientProfile(BaseModel):
    id: str
    company_name: str
    short_name: str
    tagline: Optional[str] = None
    phone: str
    email: Optional[str] = None
    website: Optional[str] = None
    service_area: str
    brand_colors: BrandColors = Field(default_factory=BrandColors)
    drive_folder_id: str = "12Ho15EiJumnZkSAPm0I1Zd9Vwe6CuLiT"
    services: List[str] = Field(default_factory=list)
    approved_claims: List[str] = Field(default_factory=list)
    manufacturer_partners: List[str] = Field(default_factory=list)
    default_cta: str = "SCHEDULE FREE ESTIMATE"

class ReferenceMetadata(BaseModel):
    id: str
    name: str
    category: str
    style: str
    layout: str
    archetype: str
    headline_position: str = "upper-left"
    cta_position: str = "bottom-bar"
    image_treatment: str = "natural"
    text_density: str = "low"
    visual_weight: str = "image-dominant"
    score: int = 90
    recommended_for: List[str] = Field(default_factory=list)
    design_principles: Dict[str, Any] = Field(default_factory=dict)
    source: str = "internal"

class AssetMetadata(BaseModel):
    asset_id: str
    category: str
    file_path: str
    source: str = "client"  # 'client', 'internal', 'unsplash'
    tags: List[str] = Field(default_factory=list)
    source_attribution: Optional[Dict[str, str]] = None

class FlyerCopy(BaseModel):
    tagline_badge: Optional[str] = None
    headline: str
    subheadline: str
    bullet_benefits: List[str] = Field(default_factory=list)
    cta_text: str
    phone: str
    website: Optional[str] = None
    service_area: Optional[str] = None
    manufacturer_note: Optional[str] = None

class FlyerSpecification(BaseModel):
    specification_id: str
    client: ClientProfile
    archetype: str
    copy_content: FlyerCopy
    background_asset: AssetMetadata
    logo_path: Optional[str] = None
    detail_asset: Optional[AssetMetadata] = None
    references_used: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    created_at: str

class QAResult(BaseModel):
    passed: bool
    score: int
    checks: Dict[str, bool] = Field(default_factory=dict)
    violations: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

class GenerationRecord(BaseModel):
    generation_id: str
    timestamp: str
    client_id: str
    campaign: str
    service: str
    archetype: str
    headline: str
    reference_ids: List[str]
    asset_ids: List[str]
    tools_used: List[str]
    renderer: str
    qa_score: int
    output_path: str
    drive_file_id: Optional[str] = None
