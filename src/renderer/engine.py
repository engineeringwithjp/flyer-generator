"""Main deterministic rendering engine for 1080x1350 flyers."""

import os
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from src.config import CANVAS_HEIGHT, CANVAS_WIDTH, OUTPUT_DIR
from src.core.models import FlyerSpecification
from src.renderer.archetypes import ArchetypeRenderer
from src.renderer.typography import TypographyManager


class FlyerRenderer:
    def __init__(self):
        self.typo = TypographyManager()
        self.archetype_renderer = ArchetypeRenderer(self.typo)

    def render_flyer(self, spec: FlyerSpecification, output_path: Optional[str] = None) -> str:
        """Renders the flyer specification to a 1080x1350 PNG."""
        # 1. Load or synthesize background image
        bg_image = self._load_or_synthesize_bg(spec.background_asset.file_path)

        # 2. Resize / crop to exact 1080x1350
        bg_image = self._fit_to_canvas(bg_image, CANVAS_WIDTH, CANVAS_HEIGHT)

        # 3. Apply archetype rendering
        final_image = self.archetype_renderer.render(spec, bg_image)

        # 4. Determine output destination
        if not output_path:
            import datetime
            now = datetime.datetime.now()
            year = now.strftime("%Y")
            day = now.strftime("%m-%d")
            out_dir = OUTPUT_DIR / year / day
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"{spec.specification_id}.png")
        else:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 5. Save as high-quality PNG
        final_image.convert("RGB").save(output_path, "PNG", quality=95)
        return output_path

    def _load_or_synthesize_bg(self, file_path: str) -> Image.Image:
        """Loads an image from file_path, or generates a photorealistic architectural base if missing."""
        if file_path and os.path.exists(file_path):
            try:
                return Image.open(file_path)
            except Exception:
                pass

        # Synthesize an architectural suburban base (Daylight sky + dark asphalt shingle roofline)
        img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (135, 165, 195))
        draw = ImageDraw.Draw(img)

        # Sky gradient
        for y in range(650):
            factor = y / 650
            r = int(120 + 70 * factor)
            g = int(155 + 60 * factor)
            b = int(200 + 40 * factor)
            draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b))

        # Architectural roof pitch (Dark Charcoal Shingles)
        roof_color = (42, 45, 50)
        draw.polygon([(0, 650), (540, 360), (1080, 650), (1080, 1350), (0, 1350)], fill=roof_color)

        # Shingle texture lines
        for y in range(400, 750, 18):
            draw.line([(0, y), (1080, y)], fill=(32, 34, 38), width=2)

        # House facade / Siding (Warm Gray / Greige Lap Siding)
        siding_color = (195, 190, 185)
        draw.rectangle([(120, 650), (960, 1350)], fill=siding_color)
        for y in range(650, 1350, 24):
            draw.line([(120, y), (960, y)], fill=(175, 170, 165), width=2)

        # Front architectural entry & trim
        draw.rectangle([(460, 880), (620, 1280)], fill=(245, 245, 245))  # White portico
        draw.rectangle([(490, 930), (590, 1280)], fill=(35, 38, 42))     # Front door

        return img

    def _fit_to_canvas(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Crops and scales image to target dimensions while maintaining aspect ratio."""
        orig_w, orig_h = img.size
        scale = max(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))
