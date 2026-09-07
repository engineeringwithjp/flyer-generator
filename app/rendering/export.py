"""Write the finished flyer to disk."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..errors import RenderError
from ..logging_setup import get_logger

log = get_logger(__name__)


def export_flyer(
    image: Image.Image,
    path: Path,
    fmt: str = "PNG",
    quality: int = 92,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.upper()
    try:
        if fmt == "PNG":
            image.save(path, format="PNG", optimize=True)
        elif fmt in {"JPG", "JPEG"}:
            # subsampling=0 keeps full chroma resolution. The default 4:2:0
            # halves it, which is invisible on photographs but puts a coloured
            # fringe around saturated type - and a flyer is mostly saturated
            # type on a photograph.
            image.convert("RGB").save(
                path,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
                subsampling=0,
            )
        else:
            raise RenderError(f"Unsupported output format {fmt!r}; use PNG or JPEG")
    except OSError as exc:
        raise RenderError(f"Could not write {path}: {exc}") from exc

    if not path.exists() or path.stat().st_size == 0:
        raise RenderError(f"Export produced an empty file at {path}")

    log.info("Wrote %s (%.0f KB)", path.name, path.stat().st_size / 1024)
    return path


def optimise_png(path: Path) -> int:
    """Re-encode a PNG at maximum compression. Returns the new size in bytes."""
    with Image.open(path) as image:
        image.load()
        image.save(path, format="PNG", optimize=True, compress_level=9)
    return path.stat().st_size


def thumbnail(path: Path, target: Path, width: int = 480) -> Path:
    """Small preview used by the GitHub Pages gallery and run summaries."""
    with Image.open(path) as handle:
        source = handle.convert("RGB")
    ratio = width / source.width
    resized = source.resize((width, int(source.height * ratio)), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    resized.save(target, format="JPEG", quality=82, optimize=True)
    return target
