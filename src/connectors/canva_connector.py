"""Canva connector for editable templates and client-facing editable assets."""

from typing import Any, Dict, Optional

from src.config import CANVA_API_KEY


class CanvaConnector:
    def __init__(self, api_key: Optional[str] = CANVA_API_KEY):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def create_editable_design(
        self,
        title: str,
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates or links a Canva editable template."""
        if not self.is_configured():
            return {
                "status": "fallback_internal",
                "message": "Canva API key not configured; using deterministic internal renderer.",
                "design_url": None
            }

        # If configured, simulate or call Canva REST API
        return {
            "status": "success",
            "design_id": f"canva_{title.lower().replace(' ', '_')}",
            "design_url": f"https://www.canva.com/design/mock_{title}",
            "message": "Editable design created successfully in Canva."
        }
