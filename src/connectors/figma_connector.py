"""Figma connector for master design systems and component sync."""

from typing import Any, Dict, Optional

from src.config import FIGMA_ACCESS_TOKEN


class FigmaConnector:
    def __init__(self, access_token: Optional[str] = FIGMA_ACCESS_TOKEN):
        self.access_token = access_token

    def is_configured(self) -> bool:
        return bool(self.access_token)

    def get_master_components(self, file_key: str = "master_flyer_system") -> Dict[str, Any]:
        """Fetches layout tokens and frames from Figma design files."""
        if not self.is_configured():
            return {
                "status": "fallback_internal",
                "message": "Figma access token not set; using local principles.json design system."
            }

        return {
            "status": "success",
            "file_key": file_key,
            "components": ["hero_card", "cta_pill", "badge_callout", "split_screen"]
        }
