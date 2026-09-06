"""Discovery and ffprobe metadata."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger(__name__)

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi"}
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".dng"}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@dataclass
class MediaItem:
    path: Path
    kind: str  # "video" | "photo"
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    duration_s: float = 0.0
    fps: float = 0.0
    codec: str = ""
    error: str = ""

    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000

    @property
    def is_4k(self) -> bool:
        return self.width >= 3000


def scan_directory(root: Path, recursive: bool = True) -> list[MediaItem]:
    """Every photo and video under ``root``. Metadata is not read yet."""
    if not root.exists():
        raise FileNotFoundError(f"Media path not found: {root}")

    walker = root.rglob("*") if recursive else root.iterdir()
    items: list[MediaItem] = []
    for path in sorted(walker):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix in VIDEO_SUFFIXES:
            kind = "video"
        elif suffix in PHOTO_SUFFIXES:
            kind = "photo"
        else:
            continue
        items.append(MediaItem(path=path, kind=kind, size_bytes=path.stat().st_size))

    log.info(
        "Discovered %d item(s) in %s (%d video, %d photo)",
        len(items),
        root,
        sum(1 for i in items if i.kind == "video"),
        sum(1 for i in items if i.kind == "photo"),
    )
    return items


def probe_video(item: MediaItem, timeout: int = 30) -> MediaItem:
    """Fill in dimensions, duration and codec via ffprobe."""
    if not ffmpeg_available():
        item.error = "ffprobe not installed"
        return item

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,codec_name",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(item.path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            item.error = (result.stderr or "ffprobe failed").strip()[:200]
            return item
        payload = json.loads(result.stdout or "{}")
    except subprocess.TimeoutExpired:
        item.error = "ffprobe timed out"
        return item
    except Exception as exc:
        item.error = f"ffprobe error: {exc}"
        return item

    streams = payload.get("streams") or [{}]
    stream = streams[0]
    item.width = int(stream.get("width") or 0)
    item.height = int(stream.get("height") or 0)
    item.codec = str(stream.get("codec_name") or "")

    rate = str(stream.get("r_frame_rate") or "0/1")
    try:
        numerator, _, denominator = rate.partition("/")
        item.fps = float(numerator) / float(denominator or 1)
    except (ValueError, ZeroDivisionError):
        item.fps = 0.0

    try:
        item.duration_s = float((payload.get("format") or {}).get("duration") or 0.0)
    except ValueError:
        item.duration_s = 0.0

    return item
