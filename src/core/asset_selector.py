"""Asset selection engine enforcing the strict 5-tier photo sourcing hierarchy."""

from pathlib import Path
from typing import List, Optional

from src.config import ASSETS_DIR, CLIENTS_DIR
from src.core.client_manager import ClientManager
from src.core.models import AssetMetadata


class AssetSelector:
    def __init__(
        self,
        clients_dir: Path = CLIENTS_DIR,
        assets_dir: Path = ASSETS_DIR,
        client_manager: Optional[ClientManager] = None
    ):
        self.clients_dir = clients_dir
        self.assets_dir = assets_dir
        self.client_manager = client_manager or ClientManager(clients_dir)

    def select_background(
        self,
        client_id: str,
        category: str,
        allow_stock: bool = False,
        photo_index: int = 0,
        exclude_asset_ids: Optional[List[str]] = None,
    ) -> AssetMetadata:
        """Selects the best available background photo adhering to Tier 1 -> Tier 5 priority."""
        # Tier 1: Client-provided project photography
        client_photos = self.client_manager.get_client_photos(client_id)
        if client_photos:
            import re
            words = set(
                w for w in re.split(r"[_\W]+", category.lower())
                if len(w) > 3 and w not in ["repair", "services", "elite", "construction"]
            )
            # Prioritize curated photos (directly in photos/, not in deep raw subdirectories)
            curated = [p for p in client_photos if Path(p).parent.name == "photos"]
            search_pool = curated if curated else client_photos

            def tokens_of(path_str: str):
                return set(t for t in re.split(r"[_\W]+", Path(path_str).stem.lower()) if t)

            matching = [p for p in search_pool if tokens_of(p).intersection(words)]
            if not matching and words:
                matching = [p for p in client_photos if tokens_of(p).intersection(words)]

            candidates = matching if matching else search_pool
            if exclude_asset_ids:
                fresh = [p for p in candidates if f"client_{Path(p).stem}" not in exclude_asset_ids]
                if fresh:
                    candidates = fresh

            selected_path = candidates[photo_index % len(candidates)]
            return AssetMetadata(
                asset_id=f"client_{Path(selected_path).stem}",
                category=category,
                file_path=selected_path,
                source="client",
                tags=["client-project", category]
            )

        # Tier 2 & 3: Approved internal background library
        cat_dir = self.assets_dir / category.lower()
        if cat_dir.exists():
            photos = [str(p) for p in cat_dir.glob("*.jpg")] + [str(p) for p in cat_dir.glob("*.png")]
            if photos:
                return AssetMetadata(
                    asset_id=f"internal_{Path(photos[0]).stem}",
                    category=category,
                    file_path=photos[0],
                    source="internal",
                    tags=["approved-background", category]
                )

        # General backgrounds
        gen_dir = self.assets_dir / "backgrounds"
        if gen_dir.exists():
            photos = [str(p) for p in gen_dir.glob("*.jpg")] + [str(p) for p in gen_dir.glob("*.png")]
            if photos:
                return AssetMetadata(
                    asset_id=f"internal_{Path(photos[0]).stem}",
                    category=category,
                    file_path=photos[0],
                    source="internal",
                    tags=["general-background"]
                )

        # Tier 5: Fallback placeholder asset if none found
        return AssetMetadata(
            asset_id="placeholder_hero",
            category=category,
            file_path="",  # Will be generated or filled by renderer
            source="internal",
            tags=["synthetic-fallback"]
        )
