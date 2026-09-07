"""The `DROP HERE` folders: one place to put pictures, one command to file them.

Three folders, one job each, named so it is obvious which is which without
reading anything:

    1 reference flyers   designs to learn the style of
    2 client photos      real job photographs to put ON a flyer
    3 drone media        straight off the SD card

HEIC is converted on the way in, because that is what a phone produces and it
is not something the operator should have to think about.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings, get_settings
from .logging_setup import get_logger

log = get_logger(__name__)

DROP_ROOT = "DROP HERE"
REFERENCES = "1 reference flyers"
CLIENT_PHOTOS = "2 client photos"
DRONE_MEDIA = "3 drone media"

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v"}


@dataclass
class IntakeReport:
    references: int = 0
    client_photos: int = 0
    drone_stills: int = 0
    drone_videos: int = 0
    converted: int = 0
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.references + self.client_photos + self.drone_stills + self.drone_videos

    def summary(self) -> str:
        if not self.total:
            return "nothing to import"
        parts = []
        if self.references:
            parts.append(f"{self.references} reference(s)")
        if self.client_photos:
            parts.append(f"{self.client_photos} client photo(s)")
        if self.drone_stills:
            parts.append(f"{self.drone_stills} drone still(s)")
        if self.drone_videos:
            parts.append(f"{self.drone_videos} drone video(s)")
        return ", ".join(parts)


def drop_root(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).paths.root / DROP_ROOT


def _convert_heic(path: Path) -> Path | None:
    """HEIC to JPEG via macOS sips. Verifies the output rather than the exit code.

    ``sips`` exits 0 even when it skipped the file, so trusting the status
    silently loses images.
    """
    target = path.with_suffix(".jpg")
    if shutil.which("sips") is None:
        return None
    subprocess.run(
        ["sips", "-s", "format", "jpeg", str(path), "--out", str(target)],
        capture_output=True,
        timeout=60,
    )
    if target.exists() and target.stat().st_size > 0:
        path.unlink(missing_ok=True)
        return target
    return None


def _files(folder: Path, suffixes: set[str]) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in suffixes and not p.name.startswith(".")
    )


def _move(path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / path.name.lower().replace(" ", "-")
    counter = 2
    while target.exists():
        target = destination / f"{target.stem}-{counter}{target.suffix}"
        counter += 1
    shutil.move(str(path), str(target))
    return target


def run_intake(
    client_id: str | None = None,
    settings: Settings | None = None,
) -> IntakeReport:
    """File everything sitting in the drop folders."""
    settings = settings or get_settings()
    client_id = client_id or settings.default_client
    report = IntakeReport()
    root = drop_root(settings)

    if not root.is_dir():
        report.notes.append(f"No '{DROP_ROOT}' folder yet. Creating it.")
        for name in (REFERENCES, CLIENT_PHOTOS, DRONE_MEDIA):
            (root / name).mkdir(parents=True, exist_ok=True)
        return report

    # HEIC first, so everything downstream is a normal image.
    for folder in (REFERENCES, CLIENT_PHOTOS, DRONE_MEDIA):
        for path in _files(root / folder, {".heic", ".heif"}):
            converted = _convert_heic(path)
            if converted:
                report.converted += 1
            else:
                report.skipped.append(f"{path.name} (could not convert from HEIC)")

    usable = IMAGE_SUFFIXES - {".heic", ".heif"}

    for path in _files(root / REFERENCES, usable):
        _move(path, settings.paths.reference_inbox)
        report.references += 1

    client_root = settings.paths.clients / client_id / "assets"
    for path in _files(root / CLIENT_PHOTOS, usable):
        _move(path, client_root / "raw" / "photos")
        report.client_photos += 1

    for path in _files(root / DRONE_MEDIA, usable):
        _move(path, client_root / "raw" / "drone")
        report.drone_stills += 1

    videos = _files(root / DRONE_MEDIA, VIDEO_SUFFIXES)
    report.drone_videos = len(videos)
    if videos:
        report.notes.append(
            f"{len(videos)} video(s) left in place. Extract frames with:  "
            f'flyer ingest-media "{root / DRONE_MEDIA}"'
        )

    if report.references:
        report.notes.append(
            "References need analysing:  flyer ingest-reference   (needs ANTHROPIC_API_KEY)"
        )
    if report.client_photos or report.drone_stills:
        report.notes.append("Then review and approve:  flyer assets --promote-top 10")

    log.info("Intake complete: %s", report.summary())
    return report
