"""Pillow helpers: validation, analysis, focal-aware cropping, contrast maths."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageStat

from ..errors import AssetError
from ..models import FocalPoint

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# Named regions expressed as fractional (left, top, right, bottom) boxes.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "top": (0.0, 0.0, 1.0, 0.33),
    "bottom": (0.0, 0.67, 1.0, 1.0),
    "left": (0.0, 0.0, 0.45, 1.0),
    "right": (0.55, 0.0, 1.0, 1.0),
    "center": (0.2, 0.3, 0.8, 0.7),
    "top-left": (0.0, 0.0, 0.5, 0.4),
    "top-right": (0.5, 0.0, 1.0, 0.4),
    "bottom-left": (0.0, 0.6, 0.5, 1.0),
    "bottom-right": (0.5, 0.6, 1.0, 1.0),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_readable(path: Path) -> None:
    """Raise AssetError unless the file is an image Pillow can decode."""
    if not path.exists():
        raise AssetError(f"Image not found: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise AssetError(
            f"Unsupported image type {path.suffix!r} ({path.name}). "
            f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    if path.stat().st_size == 0:
        raise AssetError(f"Image is empty: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:  # Pillow raises a wide variety here
        raise AssetError(f"Corrupt or unreadable image {path}: {exc}") from exc


def load_rgb(path: Path) -> Image.Image:
    ensure_readable(path)
    with Image.open(path) as image:
        return image.convert("RGB")


def region_luminance(image: Image.Image, region: str) -> tuple[float, float]:
    """Return (mean luminance 0..1, stddev 0..1) for a named region."""
    box = REGIONS.get(region, REGIONS["center"])
    width, height = image.size
    crop = image.crop(
        (
            int(box[0] * width),
            int(box[1] * height),
            max(int(box[2] * width), int(box[0] * width) + 1),
            max(int(box[3] * height), int(box[1] * height) + 1),
        )
    ).convert("L")
    stat = ImageStat.Stat(crop)
    return stat.mean[0] / 255.0, stat.stddev[0] / 255.0


def analyse_image(path: Path) -> dict:
    """Cheap, deterministic analysis used to populate an Asset record.

    ``clear_regions`` are regions calm enough (low local variance) to carry
    text without an aggressive overlay.
    """
    image = load_rgb(path)
    width, height = image.size

    grey = image.convert("L")
    stat = ImageStat.Stat(grey)
    mean_luminance = stat.mean[0] / 255.0
    contrast = min(stat.stddev[0] / 128.0, 1.0)

    clear: list[str] = []
    for name in REGIONS:
        _, stddev = region_luminance(image, name)
        if stddev < 0.16:
            clear.append(name)

    # Focal point: brightest-edge-density quadrant is a decent cheap proxy for
    # "where the subject is". Edges cluster on the subject, not the sky.
    edges = grey.filter(ImageFilter.FIND_EDGES)
    best_score, focal = -1.0, FocalPoint()
    for row in range(3):
        for col in range(3):
            box = (
                int(col * width / 3),
                int(row * height / 3),
                int((col + 1) * width / 3),
                int((row + 1) * height / 3),
            )
            score = ImageStat.Stat(edges.crop(box)).mean[0]
            if score > best_score:
                best_score = score
                focal = FocalPoint(x=(col + 0.5) / 3, y=(row + 0.5) / 3)

    return {
        "width": width,
        "height": height,
        "mean_luminance": round(mean_luminance, 4),
        "contrast": round(contrast, 4),
        "clear_regions": clear,
        "focal": focal,
        "is_portrait": height > width,
        "sha256": file_sha256(path),
    }


def crop_to_aspect(
    image: Image.Image,
    target_width: int,
    target_height: int,
    mode: str = "focal",
    focal: FocalPoint | None = None,
) -> Image.Image:
    """Cover-crop to an exact size, biased toward a crop mode or focal point."""
    if target_width <= 0 or target_height <= 0:
        raise AssetError(f"Invalid crop target {target_width}x{target_height}")

    source_width, source_height = image.size
    target_aspect = target_width / target_height
    source_aspect = source_width / source_height

    if source_aspect > target_aspect:
        new_height = source_height
        new_width = int(round(source_height * target_aspect))
    else:
        new_width = source_width
        new_height = int(round(source_width / target_aspect))

    max_left = source_width - new_width
    max_top = source_height - new_height

    anchors = {
        "center": (0.5, 0.5),
        "top": (0.5, 0.0),
        "bottom": (0.5, 1.0),
        "left": (0.0, 0.5),
        "right": (1.0, 0.5),
    }
    if mode == "focal":
        point = focal or FocalPoint()
        anchor_x, anchor_y = point.x, point.y
    else:
        anchor_x, anchor_y = anchors.get(mode, (0.5, 0.5))

    left = int(round(max_left * min(max(anchor_x, 0.0), 1.0)))
    top = int(round(max_top * min(max(anchor_y, 0.0), 1.0)))

    cropped = image.crop((left, top, left + new_width, top + new_height))
    resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
    # A touch of sharpening compensates for the downscale.
    return ImageEnhance.Sharpness(resized).enhance(1.12)
