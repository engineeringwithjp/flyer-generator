#!/usr/bin/env python3
"""Rebuild the client logo at a resolution the flyer canvas can actually use.

The only logo file that exists anywhere - the flyer repo, the website repo,
the deployed site - is 256x171. The renderer reserves 300 design-units for it,
which at the 2160px canvas is 600 real pixels, so the supplied file is less
than half the size it needs to be and Pillow's ``thumbnail`` will not enlarge.
The logo would silently render at 256px: sharp, but half the intended size.

This produces a larger raster from that one small file. It is an honest
upscale, not new detail:

* the source is a PNG that has been through JPEG at some point, so the flat
  maroon and gold are mottled - a median pass on the interior removes that
  without touching the silhouette;
* the enlargement happens on *premultiplied* colour, otherwise the black
  behind the transparent pixels bleeds a dark halo into every edge;
* a narrow unsharp pass afterwards restores the edge acutance the
  interpolation costs.

The real fix is the vector original (.ai / .eps / .svg) from whoever drew the
mark. Ask for it and this script becomes unnecessary.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

SCALE = 6  # 256 -> 1536 wide, comfortably above any canvas we render


def upscale(source: Path, target: Path, scale: int = SCALE) -> tuple[int, int]:
    image = Image.open(source).convert("RGBA")
    width, height = image.size

    r, g, b, a = image.split()

    # Premultiply so the enlargement never mixes in the colour of fully
    # transparent pixels.
    premultiplied = Image.merge(
        "RGB",
        tuple(Image.eval(Image.merge("L", (ch,)), lambda v: v) for ch in (r, g, b)),
    )
    premultiplied = Image.composite(premultiplied, Image.new("RGB", image.size, (255, 255, 255)), a)

    # Flatten JPEG mottle in the solid areas, blended back so edges survive.
    smoothed = premultiplied.filter(ImageFilter.MedianFilter(size=3))
    premultiplied = Image.blend(premultiplied, smoothed, 0.6)

    big_size = (width * scale, height * scale)
    colour = premultiplied.resize(big_size, Image.Resampling.LANCZOS)
    alpha = a.resize(big_size, Image.Resampling.LANCZOS)

    # Crisp the silhouette: interpolation spreads the alpha ramp over `scale`
    # pixels, and a steep curve pulls it back to a clean one-pixel edge.
    alpha = alpha.point([_scurve(v) for v in range(256)])

    colour = colour.filter(ImageFilter.UnsharpMask(radius=2.0, percent=70, threshold=2))

    result = Image.merge("RGBA", (*colour.split(), alpha))
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target, format="PNG", optimize=True)
    return result.size


def _scurve(value: int) -> int:
    """Steepen the alpha ramp around the halfway point."""
    x = value / 255.0
    if x <= 0.0:
        return 0
    if x >= 1.0:
        return 255
    steep = x**2 * (3 - 2 * x)  # smoothstep
    steep = steep**2 * (3 - 2 * steep)  # applied twice: sharper still
    return int(round(max(0.0, min(steep, 1.0)) * 255))


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    client = argv[1] if len(argv) > 1 else "all-elite"
    folder = root / "clients" / client / "assets" / "logo"
    if not folder.exists():
        print(f"no logo folder for client '{client}'", file=sys.stderr)
        return 1

    for name in ("logo.png", "logo-light.png"):
        source = folder / name
        if not source.exists():
            continue
        target = folder / f"{source.stem}@{SCALE}x.png"
        size = upscale(source, target)
        print(f"{name} -> {target.name}  {size[0]}x{size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
