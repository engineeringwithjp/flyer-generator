"""Typography manager for loading clean system fonts and calculating line wraps."""

import os
from typing import List, Tuple

from PIL import ImageFont


class TypographyManager:
    """Discovers and caches high-quality system fonts (Helvetica, Arial, Georgia)."""

    def __init__(self):
        self._font_cache = {}
        self._system_font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    def get_font(self, font_type: str = "sans_bold", size: int = 40) -> ImageFont.ImageFont:
        cache_key = f"{font_type}_{size}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font = None
        candidates = []
        if font_type == "sans_bold":
            candidates = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf"
            ]
        elif font_type == "serif":
            candidates = [
                "/System/Library/Fonts/Supplemental/Georgia.ttf",
                "/Library/Fonts/Georgia.ttf"
            ]
        else:  # sans_regular
            candidates = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/Library/Fonts/Arial.ttf"
            ]

        for path in candidates:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size=size)
                    break
                except Exception:
                    continue

        if font is None:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:
                font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def get_text_size(self, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
        """Returns (width, height) of rendered text."""
        bbox = font.getbbox(text)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])

    def wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        """Wraps text into lines that fit within max_width."""
        words = text.split()
        if not words:
            return []

        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            w, _ = self.get_text_size(test_line, font)
            if w <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines
