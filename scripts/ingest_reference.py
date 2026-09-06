"""Reference image intake processor."""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import REFERENCES_DIR
from src.core.models import ReferenceMetadata


def ingest_inbox_references():
    inbox_dir = REFERENCES_DIR / "inbox"
    approved_dir = REFERENCES_DIR / "approved"

    if not inbox_dir.exists():
        print(f"Inbox directory does not exist: {inbox_dir}")
        return []

    image_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    found_images = [p for p in inbox_dir.iterdir() if p.suffix.lower() in image_extensions]

    if not found_images:
        print(f"No new images in {inbox_dir}. Drop reference flyers here to analyze and ingest.")
        return []

    ingested = []
    for img_path in found_images:
        print(f"\nAnalyzing reference: {img_path.name}...")
        try:
            with Image.open(img_path) as img:
                w, h = img.size

            name_lower = img_path.stem.lower()

            # Categorize based on keywords or default to general
            if any(k in name_lower for k in ["roof", "shingle"]):
                category = "roofing"
                archetype = "hero_image"
            elif any(k in name_lower for k in ["siding", "board", "plank"]):
                category = "siding"
                archetype = "product_education"
            elif any(k in name_lower for k in ["gutter", "downspout"]):
                category = "gutters"
                archetype = "architectural_detail"
            elif any(k in name_lower for k in ["window", "door"]):
                category = "windows"
                archetype = "hero_image"
            else:
                category = "general"
                archetype = "hero_image"

            ref_id = f"ref_{category}_{img_path.stem.replace(' ', '_')}"
            dest_dir = approved_dir / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Destination paths
            dest_img = dest_dir / img_path.name
            dest_json = dest_dir / f"{ref_id}.json"

            # Move image
            shutil.move(str(img_path), str(dest_img))

            metadata = ReferenceMetadata(
                id=ref_id,
                name=img_path.stem.replace("-", " ").title(),
                category=category,
                style="premium-editorial",
                layout="hero-image",
                archetype=archetype,
                headline_position="upper-left",
                cta_position="bottom-bar",
                image_treatment="natural-photorealism",
                text_density="low",
                visual_weight="image-dominant",
                score=90,
                recommended_for=[category],
                design_principles={
                    "aspect_ratio": f"{w}:{h}",
                    "composition": "Image-first residential architecture with high negative space",
                    "typography": "High-contrast sans headline",
                    "cta_treatment": "High-contrast brand colored pill"
                },
                source="inbox_upload"
            )

            with open(dest_json, "w", encoding="utf-8") as f:
                json.dump(metadata.model_dump(), f, indent=2)

            print(f"✓ Ingested: {ref_id} -> {dest_dir.relative_to(REFERENCES_DIR)}")
            ingested.append(ref_id)
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")

    print(f"\nSuccessfully ingested {len(ingested)} reference(s).")
    return ingested

if __name__ == "__main__":
    ingest_inbox_references()
