"""Pydantic domain models. These are the contract between every layer."""

from .asset import (
    PRODUCTION_SOURCE_TYPES,
    SOURCE_RANK,
    ApprovalStatus,
    Asset,
    AssetIndex,
    FocalPoint,
    Provenance,
    SourceType,
)
from .campaign import Brief, Campaign, CampaignCatalog, CampaignPlan, PlannedFlyer
from .client import Brand, Client, Contact, DriveConfig, Offer, Product
from .flyer import (
    CanvasSpec,
    FlyerCopy,
    FlyerResult,
    FlyerSpecification,
    GenerationRun,
    ImageSpec,
    LayoutSpec,
)
from .qa import QAIssue, QAResult, Severity
from .reference import ReferenceImage, ReferenceIndex, ReferenceStatus

__all__ = [
    "PRODUCTION_SOURCE_TYPES",
    "SOURCE_RANK",
    "ApprovalStatus",
    "Asset",
    "AssetIndex",
    "Brand",
    "Brief",
    "Campaign",
    "CampaignCatalog",
    "CampaignPlan",
    "CanvasSpec",
    "Client",
    "Contact",
    "DriveConfig",
    "FlyerCopy",
    "FlyerResult",
    "FlyerSpecification",
    "FocalPoint",
    "GenerationRun",
    "ImageSpec",
    "LayoutSpec",
    "Offer",
    "PlannedFlyer",
    "Provenance",
    "SourceType",
    "Product",
    "QAIssue",
    "QAResult",
    "ReferenceImage",
    "ReferenceIndex",
    "ReferenceStatus",
    "Severity",
]
