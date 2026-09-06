"""Asset selection engine enforcing the strict 5-tier photo sourcing hierarchy."""

from pathlib import Path
from typing import Optional

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
        allow_stock: bool = False
    ) -> AssetMetadata:
        """Selects the best available background photo adhering to Tier 1 -> Tier 5 priority."""
        # Tier 1: Client-provided project photography
        client_photos = self.client_manager.get_client_photos(client_id)
        if client_photos:
            # Check for category keyword match in filename
            cat_lower = category.lower()
            matching_photos = [p for p in client_photos if cat_lower in Path(p).name.lower()]
            selected_path = matching_photos[0] if matching_photos else client_photos[0]
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
