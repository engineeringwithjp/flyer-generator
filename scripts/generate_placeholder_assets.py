#!/usr/bin/env python3
"""Generate synthetic placeholder photography so the pipeline can be exercised
before real client photos exist.

These are **not** stock photos and are **not** photorealistic. They are
procedurally drawn, clearly-labelled stand-ins that give the renderer real image
files with real luminance, contrast and negative-space characteristics, so
cropping, scrim calibration and asset scoring can all be tested end to end.

They live in ``assets/placeholders/`` and are ranked below every real asset.
Delete the folder once you have client photography.

    python scripts/generate_placeholder_assets.py
    python scripts/generate_placeholder_assets.py --clean
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "placeholders"
SIZE = (1600, 1200)

# Muted, believable Northeast-suburban palettes rather than saturated graphics.
SCENES = [
    ("roofing", "roof-asphalt-dusk", (0.32, "#2E3A45", "#6E7B86", "#3A4650", "#C08A4A")),
    ("roofing", "roof-architectural", (0.55, "#8FA6BC", "#4A5A68", "#6B7684", "#D6C9B4")),
    ("roofing", "roof-ridge-detail", (0.42, "#5C6874", "#2F3841", "#7C8794", "#B8A183")),
    ("siding", "siding-colonial", (0.62, "#A9B7C4", "#E4E7EA", "#7E8B98", "#5B6670")),
    ("siding", "siding-board-batten", (0.58, "#94A3B1", "#D8DDE2", "#6D7883", "#3F4852")),
    ("gutters", "gutter-fascia-run", (0.48, "#77848F", "#DDE3E8", "#4E5761", "#9AA6B1")),
    ("windows", "window-bay-exterior", (0.52, "#8A98A6", "#EDEFF1", "#5A646E", "#C2CBD3")),
    ("houses", "house-front-elev", (0.50, "#9BAAB8", "#E8ECEF", "#66727E", "#8C7A62")),
    ("houses", "house-golden-hour", (0.38, "#4A4038", "#C9A06A", "#6B5A48", "#E8C89A")),
    ("general", "neighbourhood-street", (0.55, "#93A2B0", "#E2E7EB", "#67727D", "#7F8B96")),
]


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _sky(draw: ImageDraw.ImageDraw, width: int, height: int, top: str, bottom: str) -> None:
    a, b = _hex(top), _hex(bottom)
    for y in range(height):
        t = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)),
        )


def _roof_planes(draw, width, height, color, accent, seed) -> None:
    rng = random.Random(seed)
    base = int(height * 0.58)
    ridge = int(height * 0.30)
    left, right = int(width * 0.08), int(width * 0.92)
    apex = (width // 2, ridge)

    draw.polygon([(left, base), apex, (right, base)], fill=_hex(color))
    # Shade one plane so the form reads three-dimensionally.
    shade = tuple(max(0, c - 26) for c in _hex(color))
    draw.polygon([(apex[0], ridge), (right, base), (apex[0], base)], fill=shade)

    # Shingle courses - regular spacing, which is what makes a roof read as real.
    course = max(int(height * 0.022), 6)
    for index, y in enumerate(range(ridge + course, base, course)):
        span = (y - ridge) / max(base - ridge, 1)
        x0 = int(apex[0] - (apex[0] - left) * span)
        x1 = int(apex[0] + (right - apex[0]) * span)
        tone = tuple(max(0, c - 10 - rng.randint(0, 12)) for c in _hex(color))
        draw.line([(x0, y), (x1, y)], fill=tone, width=2)
        offset = (index % 2) * course
        for x in range(x0 + offset, x1, course * 2):
            draw.line([(x, y), (x, min(y + course, base))], fill=tone, width=1)

    draw.line([(left, base), (right, base)], fill=_hex(accent), width=max(int(height * 0.012), 4))


def _wall_and_siding(draw, width, height, wall, trim, seed) -> None:
    rng = random.Random(seed)
    top = int(height * 0.42)
    draw.rectangle([(int(width * 0.10), top), (int(width * 0.90), height)], fill=_hex(wall))

    lap = max(int(height * 0.030), 8)
    for y in range(top + lap, height, lap):
        tone = tuple(max(0, c - 12 - rng.randint(0, 8)) for c in _hex(wall))
        draw.line([(int(width * 0.10), y), (int(width * 0.90), y)], fill=tone, width=2)

    for cx in (0.26, 0.50, 0.74):
        x0, y0 = int(width * (cx - 0.055)), int(height * 0.52)
        x1, y1 = int(width * (cx + 0.055)), int(height * 0.76)
        draw.rectangle([(x0 - 5, y0 - 5), (x1 + 5, y1 + 5)], fill=_hex(trim))
        draw.rectangle([(x0, y0), (x1, y1)], fill=(58, 68, 78))
        draw.line([((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1)], fill=_hex(trim), width=3)
        draw.line([(x0, (y0 + y1) // 2), (x1, (y0 + y1) // 2)], fill=_hex(trim), width=3)


def _gutter(draw, width, height, color) -> None:
    y = int(height * 0.42)
    thickness = max(int(height * 0.020), 7)
    draw.rectangle([(int(width * 0.08), y), (int(width * 0.92), y + thickness)], fill=_hex(color))
    for x in (0.14, 0.86):
        draw.rectangle(
            [(int(width * x), y + thickness), (int(width * x) + thickness, height)],
            fill=_hex(color),
        )


def _ground(draw, width, height, color) -> None:
    top = int(height * 0.86)
    draw.rectangle([(0, top), (width, height)], fill=_hex(color))
    draw.rectangle(
        [(int(width * 0.34), top), (int(width * 0.66), height)],
        fill=tuple(max(0, c - 22) for c in _hex(color)),
    )


def _label(image: Image.Image, text: str) -> None:
    """Mark every placeholder so it can never be mistaken for client work."""
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = image.size
    band = int(height * 0.055)
    draw.rectangle([(0, height - band), (width, height)], fill=(16, 20, 26, 210))
    draw.text((int(width * 0.02), height - band + band // 4), text, fill=(232, 236, 241, 255))


def build(scene: tuple, index: int) -> Image.Image:
    service, name, (_luma, sky_top, sky_bottom, mass, accent) = scene
    width, height = SIZE
    image = Image.new("RGB", (width, height), (200, 208, 216))
    draw = ImageDraw.Draw(image)

    _sky(draw, width, height, sky_top, sky_bottom)

    # Soft distant treeline keeps the top third from being a flat gradient.
    rng = random.Random(index * 977)
    horizon = int(height * 0.44)
    for x in range(-40, width + 40, 46):
        crown = horizon - rng.randint(20, 80)
        draw.polygon(
            [(x, horizon), (x + 23, crown), (x + 46, horizon)],
            fill=tuple(max(0, c - 34) for c in _hex(sky_bottom)),
        )

    if service == "roofing":
        _wall_and_siding(draw, width, height, mass, accent, index)
        _roof_planes(draw, width, height, mass, accent, index)
    elif service == "siding":
        _roof_planes(draw, width, height, mass, accent, index)
        _wall_and_siding(draw, width, height, sky_bottom, accent, index)
    elif service == "gutters":
        _wall_and_siding(draw, width, height, sky_bottom, accent, index)
        _gutter(draw, width, height, mass)
    elif service == "windows":
        _wall_and_siding(draw, width, height, sky_bottom, accent, index)
    else:
        _roof_planes(draw, width, height, mass, accent, index)
        _wall_and_siding(draw, width, height, sky_bottom, accent, index)

    _ground(draw, width, height, accent)

    # A gentle blur plus vignette reads more like a photograph than flat vector.
    image = image.filter(ImageFilter.GaussianBlur(radius=0.7))
    vignette = Image.new("L", (width, height), 0)
    ImageDraw.Draw(vignette).ellipse(
        (int(-width * 0.15), int(-height * 0.15), int(width * 1.15), int(height * 1.15)), fill=255
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=width // 10))
    dark = Image.new("RGB", (width, height), (12, 16, 22))
    image = Image.composite(image, dark, vignette)

    _label(image, f"SYNTHETIC PLACEHOLDER - {name} - replace with real photography")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="delete the placeholder library")
    args = parser.parse_args()

    if args.clean:
        if OUT.exists():
            shutil.rmtree(OUT)
            print(f"Removed {OUT.relative_to(ROOT)}")
        else:
            print("Nothing to clean.")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for index, scene in enumerate(SCENES):
        service, name = scene[0], scene[1]
        folder = OUT / service
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"placeholder-{name}.jpg"
        build(scene, index).save(path, "JPEG", quality=88, optimize=True)
        print(f"  + {path.relative_to(ROOT)}")
        written += 1

    (OUT / "README.md").write_text(
        "# Synthetic placeholders\n\n"
        "Procedurally generated stand-ins so the pipeline can be exercised before real\n"
        "client photography exists. They are **not** stock photos and **not**\n"
        "photorealistic. Every file is watermarked.\n\n"
        "The asset selector ranks these below every real asset. Delete this folder\n"
        "(`python scripts/generate_placeholder_assets.py --clean`) once you have\n"
        "client photography.\n",
        encoding="utf-8",
    )
    print(f"\n{written} placeholder(s) written. Run `flyer catalog` to index them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
