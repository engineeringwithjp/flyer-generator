"""Feedback loop: records approvals and rejections into design-system preferences."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import DESIGN_SYSTEM_DIR, OUTPUT_DIR


class FeedbackLearner:
    def __init__(self, preferences_path: Path = DESIGN_SYSTEM_DIR / "preferences.json"):
        self.preferences_path = preferences_path
        self.approved_dir = OUTPUT_DIR / "approved"
        self.rejected_dir = OUTPUT_DIR / "rejected"
        self.approved_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)

    def record_approval(self, flyer_path: str, archetype: str, notes: Optional[str] = None) -> None:
        """Marks flyer as approved, moves to approved archive, and boosts archetype weight."""
        src = Path(flyer_path)
        if src.exists():
            dest = self.approved_dir / src.name
            shutil.copy2(src, dest)

        self._update_preference(archetype, approved=True, note=notes)

    def record_rejection(self, flyer_path: str, archetype: str, reason: str) -> None:
        """Marks flyer as rejected, moves to rejected archive, and penalizes archetype weight."""
        src = Path(flyer_path)
        if src.exists():
            dest = self.rejected_dir / src.name
            shutil.copy2(src, dest)

        self._update_preference(archetype, approved=False, note=f"REJECTED: {reason}")

    def _update_preference(self, archetype: str, approved: bool, note: Optional[str]) -> None:
        if not self.preferences_path.exists():
            return

        try:
            with open(self.preferences_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if approved:
                data["approved_count"] = data.get("approved_count", 0) + 1
            else:
                data["rejected_count"] = data.get("rejected_count", 0) + 1

            arch_weights = data.get("preferred_archetypes", {})
            current_weight = arch_weights.get(archetype, 1.0)
            if approved:
                arch_weights[archetype] = round(current_weight + 0.1, 2)
            else:
                arch_weights[archetype] = max(0.1, round(current_weight - 0.2, 2))
            data["preferred_archetypes"] = arch_weights

            if note:
                notes = data.get("feedback_notes", [])
                notes.append(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d')}] {note}")
                data["feedback_notes"] = notes[-20:]  # Keep last 20 notes

            data["last_updated"] = datetime.now(timezone.utc).isoformat()

            with open(self.preferences_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
