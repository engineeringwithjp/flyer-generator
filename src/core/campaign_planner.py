"""Campaign planner that schedules varied, high-impact marketing angles."""

from typing import List, Optional

from src.core.history_tracker import HistoryTracker
from src.core.models import ClientProfile


class CampaignPlanner:
    def __init__(self, history_tracker: Optional[HistoryTracker] = None):
        self.history_tracker = history_tracker or HistoryTracker()

    def plan_campaigns(
        self,
        client: ClientProfile,
        count: int = 2,
        requested_campaign: Optional[str] = None,
        requested_focus: Optional[str] = None,
        requested_style: Optional[str] = None
    ) -> List[dict]:
        """Plans 1 or 2 distinct campaigns for today's generation."""
        plans = []

        # If user explicitly requested a campaign
        if requested_campaign:
            plans.append({
                "service": requested_campaign,
                "focus": requested_focus or "Full Exterior Modernization",
                "archetype": requested_style or "hero_image"
            })
            if count > 1:
                # Add a complementary second campaign (e.g. Siding + Gutters or Roofing + Siding)
                alt_service = self._pick_complementary_service(client, requested_campaign)
                plans.append({
                    "service": alt_service,
                    "focus": "Complimentary Exterior Assessment",
                    "archetype": "product_education" if "siding" in alt_service.lower() else "hero_image"
                })
            return plans[:count]

        # Automatic planning: inspect history to avoid recent service fatigue
        recent_services = self.history_tracker.get_recent_services(client.id, limit=4)
        available_services = [s for s in client.services if s not in recent_services]
        if not available_services:
            available_services = client.services

        # Select primary service
        primary_service = available_services[0] if available_services else "Roof Replacement"
        plans.append({
            "service": primary_service,
            "focus": "Residential Replacement",
            "archetype": "hero_image"
        })

        if count > 1:
            # Select secondary service
            secondary_pool = [s for s in available_services if s != primary_service]
            if not secondary_pool:
                secondary_pool = [s for s in client.services if s != primary_service]
            secondary_service = secondary_pool[0] if secondary_pool else "Composite Siding"

            archetype = "product_education" if "siding" in secondary_service.lower() else "editorial_overlay"
            plans.append({
                "service": secondary_service,
                "focus": "Built-In Thermal Insulation" if "siding" in secondary_service.lower() else "Storm Restoration",
                "archetype": archetype
            })

        return plans[:count]

    def _pick_complementary_service(self, client: ClientProfile, primary_service: str) -> str:
        primary_lower = primary_service.lower()
        for s in client.services:
            if "siding" in primary_lower and "roof" in s.lower():
                return s
            if "roof" in primary_lower and "siding" in s.lower():
                return s
            if "gutter" in primary_lower and "roof" in s.lower():
                return s
        for s in client.services:
            if s.lower() != primary_lower:
                return s
        return "Composite Siding"
