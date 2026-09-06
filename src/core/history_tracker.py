"""Generation history tracking to avoid fatigue, repetition, and duplicate campaigns."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.config import OUTPUT_DIR
from src.core.models import GenerationRecord


class HistoryTracker:
    def __init__(self, history_file: Path = OUTPUT_DIR / "history.json"):
        self.history_file = history_file
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"total_generated": 0, "last_updated": "", "records": []}, f, indent=2)

    def load_records(self) -> List[GenerationRecord]:
        with open(self.history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [GenerationRecord(**r) for r in data.get("records", [])]

    def add_record(self, record: GenerationRecord) -> None:
        with open(self.history_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = data.get("records", [])
        records.append(record.model_dump())
        data["records"] = records
        data["total_generated"] = len(records)
        data["last_updated"] = datetime.now(timezone.utc).isoformat()

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_recent_services(self, client_id: str, limit: int = 5) -> List[str]:
        """Returns the most recent service categories generated for this client."""
        records = [r for r in self.load_records() if r.client_id == client_id]
        return [r.service for r in reversed(records[-limit:])]

    def get_recent_headlines(self, client_id: str, limit: int = 10) -> List[str]:
        """Returns recent headlines to avoid phrase duplication."""
        records = [r for r in self.load_records() if r.client_id == client_id]
        return [r.headline for r in reversed(records[-limit:])]

    def is_duplicate_angle(self, client_id: str, service: str, focus: Optional[str] = None) -> bool:
        """Checks if the service was run very recently (last 2 runs)."""
        recent = self.get_recent_services(client_id, limit=2)
        return service in recent
