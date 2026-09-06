"""Client profile manager supporting multi-contractor scaling."""

import json
from pathlib import Path
from typing import List, Optional

from src.config import CLIENTS_DIR
from src.core.models import ClientProfile


class ClientManager:
    def __init__(self, clients_dir: Path = CLIENTS_DIR):
        self.clients_dir = clients_dir

    def list_clients(self) -> List[str]:
        """Returns a list of registered client IDs."""
        if not self.clients_dir.exists():
            return []
        clients = []
        for p in self.clients_dir.iterdir():
            if p.is_dir() and (p / "client.json").exists():
                clients.append(p.name)
        return sorted(clients)

    def get_client(self, client_id: str) -> ClientProfile:
        """Loads and validates a client profile by ID."""
        client_file = self.clients_dir / client_id / "client.json"
        if not client_file.exists():
            raise FileNotFoundError(f"Client profile not found: {client_file}")

        with open(client_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ClientProfile(**data)

    def get_client_logo(self, client_id: str) -> Optional[str]:
        """Finds the primary logo for a client."""
        logo_dir = self.clients_dir / client_id / "logo"
        if not logo_dir.exists():
            return None

        for ext in [".png", ".jpg", ".jpeg", ".svg"]:
            candidates = list(logo_dir.glob(f"*{ext}"))
            if candidates:
                return str(candidates[0])
        return None

    def get_client_photos(self, client_id: str) -> List[str]:
        """Finds all uploaded property photos for a client."""
        photos_dir = self.clients_dir / client_id / "photos"
        if not photos_dir.exists():
            return []

        photos = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            photos.extend([str(p) for p in photos_dir.glob(ext)])
        return sorted(photos)
