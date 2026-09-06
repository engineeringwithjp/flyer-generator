"""Copywriting engine adhering to negative rules and anti-fabrication policies."""

import re
from typing import Optional

from src.core.models import ClientProfile, FlyerCopy


class Copywriter:
    """Generates agency-grade, human-crafted construction copy with zero AI artifacts."""

    def __init__(self, client: ClientProfile):
        self.client = client

    def generate_copy(
        self,
        service: str,
        focus_topic: Optional[str] = None,
        custom_cta: Optional[str] = None,
        archetype: str = "hero_image"
    ) -> FlyerCopy:
        service_clean = service.strip()
        service_lower = service_clean.lower()
        focus = focus_topic.strip() if focus_topic else ""

        # Siding campaign
        if "siding" in service_lower:
            if "insulation" in focus.lower() or "built-in" in focus.lower():
                headline = "ENGINEERED COMFORT. TIMELESS BEAUTY."
                subheadline = "ASCEND® Composite Siding with Built-In High Density Thermal Insulation"
                bullet_benefits = [
                  "Integrated High Density Foam Barrier",
                  "Class A Fire & Wind Resistance",
                  "Zero Painting or Maintenance Required",
                  "Premium Architectural Woodgrain Profile"
                ]
                badge = "THERMAL INSULATION TECHNOLOGY"
            else:
                headline = "TRANSFORM YOUR HOME EXTERIOR."
                subheadline = "High Performance Composite Siding Built for New Jersey Weather"
                bullet_benefits = [
                  "Superior Impact & Moisture Protection",
                  "Architectural Shadow Lines & Profiles",
                  "Enhanced Year-Round Energy Efficiency",
                  "Precision Installation by Certified Specialists"
                ]
                badge = "ARCHITECTURAL SIDING"

        # Roofing campaign
        elif "roof" in service_lower:
            if "storm" in focus.lower() or "damage" in focus.lower() or "emergency" in focus.lower():
                headline = "STORM RESTORATION & INSPECTION."
                subheadline = "Comprehensive Property Assessment and Direct Insurance Claims Navigation"
                bullet_benefits = [
                  "Free 21-Point Exterior Roof Inspection",
                  "Emergency Leak Barrier & Tarping Service",
                  "Architectural Impact-Rated Shingles",
                  "Certified Master Installation Specialists"
                ]
                badge = "EMERGENCY RESTORATION"
            elif "winter" in focus.lower() or "protect" in focus.lower():
                headline = "PROTECT YOUR HOME BEFORE WINTER."
                subheadline = "Architectural Roof Replacement Engineered for Heavy Snow and Ice Dams"
                bullet_benefits = [
                  "Advanced Ice & Water Leak Barrier Protection",
                  "High-Velocity Wind Resistance up to 130 MPH",
                  "Full Roof Deck Inspection & Ventilation",
                  "Clean Jobsite Guarantee with Magnetic Sweep"
                ]
                badge = "WINTER READINESS"
            else:
                headline = "YOUR ROOF DESERVES BETTER."
                subheadline = "Precision Roof Replacement Built to Endure for Generations"
                bullet_benefits = [
                  "Premium Architectural Asphalt Shingles",
                  "Complete 5-Part Roof Defense System",
                  "Certified Master Elite Installation",
                  "Complimentary Written Property Estimate"
                ]
                badge = "MASTER ROOFING SPECIALISTS"

        # Gutters campaign
        elif "gutter" in service_lower:
            headline = "PROTECT YOUR HOME FOUNDATION."
            subheadline = "Heavy Gauge Seamless Gutters and High-Flow Micro-Mesh Shield Systems"
            bullet_benefits = [
              "Custom On-Site Seamless Fabrication",
              "Prevents Basement Flooding & Fascia Rot",
              "Clog-Free Leaf Guard Technology",
              "Color-Matched to Your Existing Trim"
            ]
            badge = "SEAMLESS WATER DRAINAGE"

        # Windows / Doors
        elif "window" in service_lower:
            headline = "SUPERIOR THERMAL PERFORMANCE."
            subheadline = "Custom Replacement Windows with Advanced Argon Gas Insulation"
            bullet_benefits = [
              "Multi-Chamber Fusion-Welded Vinyl Frames",
              "Low-E Glass Coatings Reduce Energy Loss",
              "Whisper-Quiet Sound Dampening Barrier",
              "Precision Air-Tight Perimeter Seal"
            ]
            badge = "ENERGY EFFICIENCY"

        # Before & After / General Exterior Remodeling
        else:
            headline = "BUILT WITH PRIDE. BUILT TO LAST."
            subheadline = "Complete Residential Exterior Transformations in Northern New Jersey"
            bullet_benefits = [
              "Turnkey Roofing, Siding & Gutter Renovations",
              "Complimentary 21-Point Property Inspection",
              "Certified Craftsmen on Every Project",
              "Clean Jobsite Guarantee with Magnetic Sweeps"
            ]
            badge = "EXTERIOR REMODELING"

        # Check for manufacturer note if relevant
        manufacturer_note = None
        if "ascend" in subheadline.lower():
            manufacturer_note = "Installed by All Elite Construction | Authorized Installer"

        cta = custom_cta or self.client.default_cta

        # Rigorous anti-AI sanitization
        headline = self._sanitize_text(headline)
        subheadline = self._sanitize_text(subheadline)
        bullet_benefits = [self._sanitize_text(b) for b in bullet_benefits]
        cta = self._sanitize_text(cta)

        return FlyerCopy(
            tagline_badge=badge,
            headline=headline,
            subheadline=subheadline,
            bullet_benefits=bullet_benefits,
            cta_text=cta,
            phone=self.client.phone,
            website=self.client.website,
            service_area=self.client.service_area,
            manufacturer_note=manufacturer_note
        )

    def _sanitize_text(self, text: str) -> str:
        """Removes em dashes, double hyphens, and emojis."""
        # Replace em dash or en dash with period or pipe
        text = text.replace("—", " | ").replace("–", " - ").replace("--", " - ")
        # Remove emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub(r"", text)
        return text.strip()
