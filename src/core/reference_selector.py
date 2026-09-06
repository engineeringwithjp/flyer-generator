"""Reference selector and multi-reference blending engine."""

import json
from pathlib import Path
from typing import List, Optional

from src.config import REFERENCES_DIR
from src.core.models import ReferenceMetadata


class ReferenceSelector:
    def __init__(self, references_dir: Path = REFERENCES_DIR):
        self.references_dir = references_dir

    def load_all_references(self) -> List[ReferenceMetadata]:
        refs = []
        # Search approved and experimental
        for category_dir in [self.references_dir / "approved", self.references_dir / "experimental"]:
            if not category_dir.exists():
                continue
            for json_file in category_dir.glob("**/*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    refs.append(ReferenceMetadata(**data))
                except Exception:
                    continue
        return refs

    def get_rejected_ids(self) -> List[str]:
        rejected_dir = self.references_dir / "rejected"
        rejected = []
        if rejected_dir.exists():
            for json_file in rejected_dir.glob("**/*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    rejected.append(data.get("id"))
                except Exception:
                    continue
        return [r for r in rejected if r]

    def select_reference(
        self,
        category: str,
        preferred_archetype: Optional[str] = None
    ) -> ReferenceMetadata:
        """Selects the highest scoring approved reference for a category."""
        all_refs = self.load_all_references()
        rejected_ids = set(self.get_rejected_ids())

        # Filter out rejected
        eligible = [r for r in all_refs if r.id not in rejected_ids]

        # Prioritize category match
        cat_matches = [
            r for r in eligible
            if r.category.lower() == category.lower()
            or any(category.lower() in rec.lower() for rec in r.recommended_for)
        ]

        pool = cat_matches if cat_matches else eligible

        if preferred_archetype:
            archetype_matches = [r for r in pool if r.archetype == preferred_archetype]
            if archetype_matches:
                pool = archetype_matches

        if not pool:
            # Fallback default reference
            return ReferenceMetadata(
                id="ref_fallback_hero",
                name="Default Architectural Hero",
                category=category,
                style="premium-editorial",
                layout="hero-image",
                archetype=preferred_archetype or "hero_image",
                headline_position="upper-left",
                cta_position="bottom-bar",
                image_treatment="natural",
                text_density="low",
                visual_weight="image-dominant",
                score=85,
                recommended_for=[category],
                design_principles={"composition": "House as hero with sky negative space"}
            )

        # Sort by score descending
        pool.sort(key=lambda x: x.score, reverse=True)
        return pool[0]
