"""Unsplash connector for supplemental photography when client assets are missing."""

from typing import Optional

from src.config import UNSPLASH_ACCESS_KEY
from src.core.models import AssetMetadata


class UnsplashConnector:
    def __init__(self, access_key: Optional[str] = UNSPLASH_ACCESS_KEY):
        self.access_key = access_key

    def is_configured(self) -> bool:
        return bool(self.access_key)

    def search_photo(self, query: str, category: str = "roofing") -> Optional[AssetMetadata]:
        """Searches Unsplash for architectural construction photos, falling back gracefully."""
        if not self.is_configured():
            # Graceful offline mode
            return None

        try:
            import requests
            headers = {"Authorization": f"Client-ID {self.access_key}"}
            params = {
                "query": f"{query} house exterior architecture",
                "orientation": "portrait",
                "per_page": 1
            }
            resp = requests.get("https://api.unsplash.com/search/photos", headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    photo = results[0]
                    return AssetMetadata(
                        asset_id=f"unsplash_{photo.get('id')}",
                        category=category,
                        file_path=photo.get("urls", {}).get("regular", ""),
                        source="unsplash",
                        tags=["unsplash-stock", category],
                        source_attribution={
                            "source": "unsplash",
                            "source_id": photo.get("id"),
                            "photographer": photo.get("user", {}).get("name", "Unsplash Contributor"),
                            "source_url": photo.get("links", {}).get("html", "")
                        }
                    )
        except Exception:
            return None

        return None
