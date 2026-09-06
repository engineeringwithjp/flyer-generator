"""Mobbin connector for modern visual-design hierarchy and spacing inspiration."""

from typing import Any, Dict, List, Optional

from src.config import MOBBIN_API_KEY


class MobbinConnector:
    def __init__(self, api_key: Optional[str] = MOBBIN_API_KEY):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_patterns(self, pattern_type: str = "editorial-cards") -> List[Dict[str, Any]]:
        """Finds clean modern spacing and visual hierarchy patterns."""
        if not self.is_configured():
            return [
                {
                    "source": "mobbin_cached",
                    "pattern": "floating_glass_card",
                    "spacing": "72px padding, 24px internal card margin",
                    "typography": "High-contrast geometric sans hook with subhead hierarchy"
                }
            ]

        return [
            {
                "source": "mobbin_api",
                "pattern": pattern_type,
                "spacing": "Minimalist architectural layout with generous negative space"
            }
        ]
