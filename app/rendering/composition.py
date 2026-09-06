"""Colour maths, gradients, shapes and the layout grid.

Everything here is pure and deterministic: the same specification always
produces the same pixels.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


# ------------------------------------------------------------------- colour


def hex_to_rgb(value: str) -> RGB:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"{value!r} is not a hex colour")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def relative_luminance(color: str | RGB) -> float:
    """WCAG relative luminance, 0 (black) .. 1 (white)."""
    rgb = hex_to_rgb(color) if isinstance(color, str) else color

    def channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str | RGB, b: str | RGB) -> float:
    """WCAG contrast ratio, 1.0 .. 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def best_text_color(
    background: str | RGB, options: tuple[str, str] = ("#FFFFFF", "#101418")
) -> str:
    """Pick whichever of two inks reads better on this background."""
    return max(options, key=lambda ink: contrast_ratio(ink, background))


def mix(a: str | RGB, b: str | RGB, ratio: float) -> RGB:
    """Linear blend; ratio 0 returns a, 1 returns b."""
    ra, ga, ba = hex_to_rgb(a) if isinstance(a, str) else a
    rb, gb, bb = hex_to_rgb(b) if isinstance(b, str) else b
    t = min(max(ratio, 0.0), 1.0)
    return (
        int(round(ra + (rb - ra) * t)),
        int(round(ga + (gb - ga) * t)),
        int(round(ba + (bb - ba) * t)),
    )


def darken(color: str | RGB, amount: float) -> RGB:
    return mix(color, (0, 0, 0), amount)


def lighten(color: str | RGB, amount: float) -> RGB:
    return mix(color, (255, 255, 255), amount)


# ------------------------------------------------------------------ gradients


def vertical_gradient(
    size: tuple[int, int],
    top: RGBA,
    bottom: RGBA,
    stops: tuple[float, float] = (0.0, 1.0),
) -> Image.Image:
    """RGBA gradient. ``stops`` clamps the ramp to part of the height."""
    width, height = size
    gradient = Image.new("RGBA", (1, height))
    pixels = gradient.load()
    assert pixels is not None  # Pillow only returns None for an unloadable image
    start, end = stops
    span = max(end - start, 1e-6)
    for y in range(height):
        t = (y / max(height - 1, 1) - start) / span
        t = min(max(t, 0.0), 1.0)
        pixels[0, y] = tuple(int(round(top[i] + (bottom[i] - top[i]) * t)) for i in range(4))  # type: ignore[assignment]
    return gradient.resize((width, height), Image.Resampling.BILINEAR)


def diagonal_gradient(size: tuple[int, int], top: RGBA, bottom: RGBA) -> Image.Image:
    gradient = vertical_gradient((size[0], size[1]), top, bottom)
    return gradient.rotate(-12, resample=Image.Resampling.BILINEAR, expand=False)


def radial_vignette(size: tuple[int, int], strength: float = 0.5) -> Image.Image:
    """Soft darkening toward the corners."""
    width, height = size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    inset_x, inset_y = int(width * 0.08), int(height * 0.08)
    draw.ellipse((inset_x, inset_y, width - inset_x, height - inset_y), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(width, height) // 8))
    layer = Image.new("RGBA", (width, height), (0, 0, 0, int(255 * strength)))
    layer.putalpha(Image.eval(mask, lambda v: int((255 - v) * strength)))
    return layer


# --------------------------------------------------------------------- shapes


def rounded_rect(size: tuple[int, int], radius: int, fill: RGBA) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=fill)
    return layer


def diagonal_panel(
    size: tuple[int, int],
    fill: RGBA,
    split_y: float,
    slope: float = 0.09,
    top: bool = False,
) -> Image.Image:
    """A panel with one angled edge. ``split_y`` is the fractional midpoint."""
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    mid = height * split_y
    rise = height * slope / 2
    if top:
        polygon = [(0, 0), (width, 0), (width, mid + rise), (0, mid - rise)]
    else:
        polygon = [(0, mid - rise), (width, mid + rise), (width, height), (0, height)]
    draw.polygon(polygon, fill=fill)
    return layer


def accent_bar(width: int, height: int, color: RGB) -> Image.Image:
    layer = Image.new("RGBA", (width, height), (*color, 255))
    return layer


# ----------------------------------------------------------------------- grid


@dataclass(frozen=True)
class Grid:
    """Safe-area grid. Every layout positions against this, never raw pixels."""

    width: int
    height: int
    margin_ratio: float = 0.074  # 80px at 1080 wide

    @property
    def margin(self) -> int:
        return int(round(self.width * self.margin_ratio))

    @property
    def left(self) -> int:
        return self.margin

    @property
    def right(self) -> int:
        return self.width - self.margin

    @property
    def top(self) -> int:
        return self.margin

    @property
    def bottom(self) -> int:
        return self.height - self.margin

    @property
    def content_width(self) -> int:
        return self.right - self.left

    @property
    def content_height(self) -> int:
        return self.bottom - self.top

    def scale(self, value: float) -> int:
        """Scale a design value authored at 1080px wide to this canvas."""
        return int(round(value * self.width / 1080))

    def y(self, fraction: float) -> int:
        return int(round(self.height * fraction))

    def x(self, fraction: float) -> int:
        return int(round(self.width * fraction))
