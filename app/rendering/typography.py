"""Font resolution and automatic text fitting.

Fonts are resolved in three tiers so the renderer works everywhere:

1. ``assets/fonts/`` - fonts fetched by ``scripts/fetch_fonts.py`` (preferred)
2. well-known system font paths (macOS / Linux / Windows)
3. Pillow's bundled scalable default (ugly but never fails)

``fit_text`` shrinks and wraps until the text fits its box, so an overlong
headline degrades gracefully instead of overflowing the canvas.
"""

from __future__ import annotations

import contextlib
import platform
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import ImageDraw, ImageFont

from ..config import get_settings
from ..logging_setup import get_logger

log = get_logger(__name__)

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Logical role -> ordered list of preferred file stems in assets/fonts/.
# Ordered by preference. All Elite's brand faces (Barlow Condensed + Lato) come
# first so the flyers match the live website's type system.
ROLE_FILES: dict[str, tuple[str, ...]] = {
    "display": ("BarlowCondensed-Bold", "Anton-Regular", "Oswald-Bold", "Archivo-Black"),
    "headline": ("BarlowCondensed-Bold", "Anton-Regular", "Oswald-Bold", "Lato-Black"),
    "subhead": ("Lato-Regular", "BarlowCondensed-SemiBold", "Lato-Bold", "Inter-Regular"),
    "body": ("Lato-Regular", "Inter-Regular", "BarlowCondensed-Medium"),
    "bold": ("Lato-Bold", "BarlowCondensed-Bold", "Lato-Black", "Inter-Bold"),
}

# Tier 2: system fonts that exist on the platforms this runs on.
SYSTEM_FALLBACKS: dict[str, tuple[str, ...]] = {
    "Darwin": (
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ),
    "Linux": (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    "Windows": (
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ),
}

BOLD_ROLES = {"display", "headline", "bold"}


@dataclass(frozen=True)
class FittedText:
    lines: list[str]
    font: Font
    size: int
    width: int
    height: int
    line_height: int


def load_pairings() -> dict:
    """Type pairings from ``config/typography.json``."""
    from ..config import load_json_config

    try:
        return load_json_config("typography.json")
    except Exception as exc:  # pragma: no cover - config is shipped
        log.warning("Could not load typography.json (%s); using built-in roles", exc)
        return {"default": "condensed-editorial", "pairings": {}}


def list_pairings() -> list[str]:
    return sorted(load_pairings().get("pairings", {}))


def pairings_for_style(style: str) -> list[str]:
    """Which pairings suit a given visual style, best first."""
    pairings = load_pairings().get("pairings", {})
    suited = [name for name, cfg in pairings.items() if style in cfg.get("suits", [])]
    return suited or list(pairings)


class FontLibrary:
    """Resolves logical roles to concrete font files, once per process.

    A ``pairing`` name selects a type system from ``config/typography.json`` so
    that different flyers genuinely look like different pieces of design rather
    than one template with the words swapped.
    """

    def __init__(self, fonts_dir: Path | None = None, pairing: str | None = None) -> None:
        self.fonts_dir = fonts_dir or get_settings().paths.fonts
        self._warned: set[str] = set()
        config = load_pairings()
        self.pairing_name = pairing or config.get("default", "condensed-editorial")
        self.pairing = config.get("pairings", {}).get(self.pairing_name, {})
        self.tracking_scale = float(self.pairing.get("tracking_scale", 1.0))

    def _role_stems(self, role: str) -> tuple[str, ...]:
        """Pairing stems first, then the global fallback order."""
        pairing_roles = self.pairing.get("roles", {}).get(role, [])
        return tuple(pairing_roles) + ROLE_FILES.get(role, ())

    @lru_cache(maxsize=128)  # noqa: B019 - one library per render, bounded roles
    def _resolve_path(self, role: str, bold_hint: bool) -> str | None:
        for stem in self._role_stems(role):
            for suffix in (".ttf", ".otf"):
                candidate = self.fonts_dir / f"{stem}{suffix}"
                if candidate.exists():
                    return str(candidate)

        # Any font the user dropped in, preferring bold-looking names for headings.
        if self.fonts_dir.exists():
            available = sorted([*self.fonts_dir.glob("*.ttf"), *self.fonts_dir.glob("*.otf")])
            if available:
                if bold_hint:
                    heavy = [
                        p
                        for p in available
                        if any(k in p.stem.lower() for k in ("bold", "black", "heavy", "anton"))
                    ]
                    if heavy:
                        return str(heavy[0])
                return str(available[0])

        for path in SYSTEM_FALLBACKS.get(platform.system(), ()):
            if Path(path).exists():
                if bold_hint and not any(
                    k in Path(path).name.lower() for k in ("impact", "black", "bold")
                ):
                    continue
                return path
        # Second pass without the bold requirement.
        for path in SYSTEM_FALLBACKS.get(platform.system(), ()):
            if Path(path).exists():
                return path
        return None

    def get(self, role: str, size: int) -> Font:
        size = max(int(size), 6)
        path = self._resolve_path(role, role in BOLD_ROLES)
        if path:
            try:
                font = ImageFont.truetype(path, size)
                _apply_weight(font, path, role)
                return font
            except OSError as exc:  # pragma: no cover - corrupt font file
                log.warning("Could not load font %s: %s", path, exc)
        if role not in self._warned:
            log.warning(
                "No font file found for role %r - using Pillow's default. "
                "Run `python scripts/fetch_fonts.py` for production-quality type.",
                role,
            )
            self._warned.add(role)
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # pragma: no cover - very old Pillow
            return ImageFont.load_default()

    def available(self) -> list[str]:
        if not self.fonts_dir.exists():
            return []
        return sorted(p.name for p in self.fonts_dir.iterdir() if p.suffix in {".ttf", ".otf"})


# Weight to request on a variable font, per role. Without this Pillow renders a
# variable font at its default instance, which is usually Regular, so a file
# named "-Bold" would come out thin.
ROLE_WEIGHT = {
    "display": 800,
    "headline": 800,
    "bold": 700,
    "subhead": 500,
    "body": 400,
}


def _apply_weight(font: Font, path: str, role: str) -> None:
    """Set the weight axis on a variable font. A no-op for static fonts.

    Pillow only exposes the variation API on ``FreeTypeFont``, and even there
    only when the build has FreeType's multiple-master support, so everything
    is reached through ``getattr`` and the axis dictionaries are treated as
    untyped data.
    """
    setter = getattr(font, "set_variation_by_axes", None)
    reader = getattr(font, "get_variation_axes", None)
    if not callable(setter) or not callable(reader):
        return
    try:
        axes: list[dict[str, Any]] = list(reader())
    except Exception:
        return  # static font, or FreeType built without variation support
    if not axes:
        return

    target = ROLE_WEIGHT.get(role, 400)
    values: list[float] = []
    for axis in axes:
        raw_name = axis.get("name", "")
        name = raw_name.decode(errors="ignore") if isinstance(raw_name, bytes) else str(raw_name)
        minimum = _as_float(axis.get("minimum"), 0.0)
        maximum = _as_float(axis.get("maximum"), 0.0)
        if "wght" in name.lower() or "weight" in name.lower():
            values.append(max(minimum, min(float(target), maximum)))
        else:
            values.append(_as_float(axis.get("default"), minimum))
    with contextlib.suppress(Exception):  # unusual axis layout
        setter(values)


def _as_float(value: object, fallback: float) -> float:
    """Coerce a FreeType axis bound to a float, falling back when absent."""
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


_MEASURE_IMAGE_DRAW: ImageDraw.ImageDraw | None = None


def _draw() -> ImageDraw.ImageDraw:
    global _MEASURE_IMAGE_DRAW
    if _MEASURE_IMAGE_DRAW is None:
        from PIL import Image

        _MEASURE_IMAGE_DRAW = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    return _MEASURE_IMAGE_DRAW


def measure(text: str, font: Font) -> tuple[int, int]:
    """Pixel width/height of a single line."""
    if not text:
        return 0, 0
    left, top, right, bottom = _draw().textbbox((0, 0), text, font=font)
    return int(right - left), int(bottom - top)


def wrap_text(text: str, font: Font, max_width: int) -> list[str]:
    """Greedy word wrap. Words longer than the box are hard-split."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if measure(candidate, font)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    lines = _rebalance_last_line(lines, font, max_width)

    hard_wrapped: list[str] = []
    for line in lines:
        while measure(line, font)[0] > max_width and len(line) > 1:
            cut = len(line)
            while cut > 1 and measure(line[:cut], font)[0] > max_width:
                cut -= 1
            hard_wrapped.append(line[:cut])
            line = line[cut:]
        hard_wrapped.append(line)
    return hard_wrapped


def _rebalance_last_line(lines: list[str], font: Font, max_width: int) -> list[str]:
    """Pull a word down so the last line is never a lone orphan.

    Greedy wrapping packs each line as full as it will go, which regularly
    leaves the final line holding one short word - "THE PUDDLE BY THE
    FOUNDATION IS A / CLUE". It is not a fitting error, so nothing downstream
    catches it; it just looks like nobody set the type. Moving the last word
    of the previous line down costs nothing and fixes it, as long as the
    previous line still has words to spare and the move does not overflow.
    """
    if len(lines) < 2:
        return lines
    last = lines[-1].split()
    previous = lines[-2].split()
    # Only an orphan: one short word alone on the final line.
    if len(last) != 1 or len(last[0]) > 6 or len(previous) < 3:
        return lines

    moved = previous[-1]
    if measure(f"{moved} {lines[-1]}", font)[0] > max_width:
        return lines
    return [*lines[:-2], " ".join(previous[:-1]), f"{moved} {lines[-1]}"]


def fit_text(
    text: str,
    library: FontLibrary,
    role: str,
    max_width: int,
    max_height: int,
    max_size: int,
    min_size: int = 14,
    line_spacing: float = 1.06,
    max_lines: int | None = None,
) -> FittedText:
    """Largest size at which ``text`` fits the box. Never returns overflow."""
    text = " ".join(text.split())
    if not text:
        font = library.get(role, min_size)
        return FittedText([], font, min_size, 0, 0, min_size)

    size = max(max_size, min_size)
    best: FittedText | None = None
    while size >= min_size:
        font = library.get(role, size)
        lines = wrap_text(text, font, max_width)
        line_height = int(round(size * line_spacing))
        total_height = line_height * len(lines)
        widest = max((measure(line, font)[0] for line in lines), default=0)
        fits_lines = max_lines is None or len(lines) <= max_lines
        if total_height <= max_height and widest <= max_width and fits_lines:
            best = FittedText(lines, font, size, widest, total_height, line_height)
            break
        size -= 2

    if best is None:
        font = library.get(role, min_size)
        lines = wrap_text(text, font, max_width)
        if max_lines:
            lines = lines[:max_lines]
        line_height = int(round(min_size * line_spacing))
        best = FittedText(
            lines,
            font,
            min_size,
            max((measure(line, font)[0] for line in lines), default=0),
            line_height * len(lines),
            line_height,
        )
        log.warning("Text did not fit at the minimum size and was clamped: %r", text[:60])
    return best


def draw_lines(
    draw: ImageDraw.ImageDraw,
    fitted: FittedText,
    x: int,
    y: int,
    fill: tuple[int, int, int],
    align: str = "left",
    box_width: int | None = None,
    tracking: int = 0,
) -> int:
    """Draw a fitted block and return the y coordinate just below it."""
    cursor = y
    for line in fitted.lines:
        line_width = measure(line, fitted.font)[0]
        if align == "center" and box_width:
            start_x = x + (box_width - line_width) // 2
        elif align == "right" and box_width:
            start_x = x + box_width - line_width
        else:
            start_x = x
        if tracking:
            _draw_tracked(draw, line, start_x, cursor, fitted.font, fill, tracking)
        else:
            draw.text((start_x, cursor), line, font=fitted.font, fill=fill)
        cursor += fitted.line_height
    return cursor


def _draw_tracked(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: Font,
    fill: tuple[int, int, int],
    tracking: int,
) -> None:
    """Letter-spaced text - Pillow has no native tracking."""
    cursor = x
    for char in text:
        draw.text((cursor, y), char, font=font, fill=fill)
        cursor += measure(char, font)[0] + tracking


def tracked_width(text: str, font: Font, tracking: int) -> int:
    return sum(measure(c, font)[0] + tracking for c in text) - tracking if text else 0
