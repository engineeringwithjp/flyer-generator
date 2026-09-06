"""Google Drive for Desktop as the output destination.

The simplest way to keep generated flyers off the Mac's own storage is to write
them into the mounted Drive folder in the first place. With Drive set to
"stream files" they occupy no local space at all; with "mirror" they occupy the
same space they would anywhere, but they are at least in the client's folder
rather than buried in Documents.

This needs no API credentials and no OAuth. It is the recommended path for a
single operator on a Mac; the API uploader in ``uploader.py`` remains the path
for GitHub Actions, which has no Drive mount.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from ..config import Settings, get_settings
from ..errors import DriveError
from ..logging_setup import get_logger

log = get_logger(__name__)

CLOUD_STORAGE = Path.home() / "Library" / "CloudStorage"


def find_drive_mounts() -> list[Path]:
    """Every Google Drive for Desktop mount on this machine."""
    if not CLOUD_STORAGE.exists():
        return []
    mounts = []
    for entry in sorted(CLOUD_STORAGE.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("GoogleDrive-"):
            continue
        my_drive = entry / "My Drive"
        if my_drive.is_dir():
            mounts.append(my_drive)
    return mounts


def find_folder(name: str, mount: Path | None = None) -> Path | None:
    """Locate a folder by name inside a Drive mount.

    Searched shallowly on purpose: a Drive mount can be enormous, and a deep
    walk would stall on files that are streamed rather than downloaded.
    """
    mounts = [mount] if mount else find_drive_mounts()
    for root in mounts:
        if not root or not root.exists():
            continue
        direct = root / name
        if direct.is_dir():
            return direct
        try:
            for parent in root.iterdir():
                if not parent.is_dir() or parent.name.startswith("."):
                    continue
                candidate = parent / name
                if candidate.is_dir():
                    return candidate
        except OSError:
            continue
    return None


def is_available(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    path = settings.drive_local_path
    return bool(path) and Path(str(path)).expanduser().is_dir()


def resolve_output_dir(
    company_name: str,
    when: date,
    settings: Settings | None = None,
) -> Path | None:
    """The Drive folder today's flyers should be written into.

    Mirrors the API uploader's layout so both paths produce the same tree:
    ``<root>/Flyers/<YYYY>/<Month>/<MM-DD>``.
    """
    settings = settings or get_settings()
    if not settings.drive_local_path:
        return None

    root = Path(str(settings.drive_local_path)).expanduser()
    if not root.is_dir():
        log.warning(
            "DRIVE_LOCAL_PATH is set to %s but that folder does not exist. "
            "Is Google Drive for Desktop running?",
            root,
        )
        return None

    target = root / "Flyers" / when.strftime("%Y") / when.strftime("%B") / when.strftime("%m-%d")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DriveError(f"Could not create {target}: {exc}") from exc

    _ = company_name  # the root folder is already client-scoped
    return target


def describe(settings: Settings | None = None) -> dict[str, object]:
    """Status for `flyer drive-setup`."""
    settings = settings or get_settings()
    mounts = find_drive_mounts()
    configured = settings.drive_local_path
    return {
        "mounts_found": [str(m) for m in mounts],
        "configured_path": configured or "",
        "configured_exists": bool(configured) and Path(str(configured)).expanduser().is_dir(),
        "streaming_hint": _streaming_hint(),
    }


def _streaming_hint() -> str:
    """Whether Drive is streaming or mirroring decides if files use local disk."""
    return (
        "Google Drive > Settings > Preferences > My Drive: choose "
        "'Stream files' so flyers use no local disk, or 'Mirror files' to keep "
        "offline copies."
    )


def suggest_env_line(folder: Path) -> str:
    return f'DRIVE_LOCAL_PATH="{folder}"'


def _expand(value: str) -> Path:
    return Path(os.path.expanduser(value))
