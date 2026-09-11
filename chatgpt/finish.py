"""Composite the supplied logo/contact text onto native ChatGPT artwork.

No image-generation API, network access, scheduling, or Nano Banana dependency.
Run with a temporary input/output directory; delete copies after Drive verification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def finish(source: Path, logo_path: Path, destination: Path) -> None:
    # A uniform scale preserves all architectural proportions. When the native
    # tool returns a nearby ratio, use quiet paper margins instead of stretching.
    paper = (251, 248, 241)
    canvas = Image.new("RGB", (1080, 1350), paper)
    with Image.open(source) as image:
        artwork = ImageOps.contain(
            ImageOps.exif_transpose(image).convert("RGB"),
            canvas.size,
            Image.Resampling.LANCZOS,
        )
    canvas.paste(artwork, ((1080 - artwork.width) // 2, 0))
    with Image.open(logo_path) as original:
        logo = original.convert("RGBA")
        bounds = logo.getchannel("A").getbbox()
        if not bounds:
            raise ValueError("The original logo is empty")
        logo = ImageOps.contain(logo.crop(bounds), (230, 138), Image.Resampling.LANCZOS)
        canvas.paste(logo, (780 + (230 - logo.width) // 2, 28), logo)

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 1214, 1080, 1350), fill=paper)
    draw.line((68, 1220, 1012, 1220), fill="#762738", width=1)
    lines = (
        ("(551) 335-9235  |  alleliteconstructioncorpnj.com", 25),
        ("@alleliteroofing  |  info@alleliteconstructioncorpnj.com", 22),
        ("131 Main St STE 122, Hackensack, NJ 07601", 22),
    )
    for row, (text, size) in enumerate(lines):
        selected = font(size)
        while draw.textlength(text, font=selected) > 944 and size > 14:
            size -= 1
            selected = font(size)
        draw.text((540, 1251 + row * 33), text, font=selected, anchor="mm", fill="#2B2325")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, "JPEG", quality=96, subsampling=0, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--logo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for post in json.loads(args.manifest.read_text()):
        destination = args.output / post["name"]
        finish(Path(post["generated_path"]), args.logo, destination)
        print(destination)


if __name__ == "__main__":
    main()
