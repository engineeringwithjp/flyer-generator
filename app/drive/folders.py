"""Drive folder discovery and creation, with an in-run cache."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..errors import DriveError
from ..logging_setup import get_logger

log = get_logger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"


def _escape(name: str) -> str:
    return name.replace("\\", "\\\\").replace("'", "\\'")


def find_child(service: Any, parent_id: str, name: str, shared_drive: bool = False) -> str | None:
    query = (
        f"name = '{_escape(name)}' and '{parent_id}' in parents "
        f"and mimeType = '{FOLDER_MIME}' and trashed = false"
    )
    kwargs: dict[str, Any] = {
        "q": query,
        "fields": "files(id, name)",
        "pageSize": 10,
        "spaces": "drive",
    }
    if shared_drive:
        kwargs.update(supportsAllDrives=True, includeItemsFromAllDrives=True)
    response = service.files().list(**kwargs).execute()
    files = response.get("files", [])
    return files[0]["id"] if files else None


def create_child(service: Any, parent_id: str, name: str, shared_drive: bool = False) -> str:
    metadata = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    kwargs: dict[str, Any] = {"body": metadata, "fields": "id"}
    if shared_drive:
        kwargs["supportsAllDrives"] = True
    created = service.files().create(**kwargs).execute()
    log.info("Created Drive folder %r", name)
    return created["id"]


def ensure_folder_path(
    service: Any,
    root_id: str,
    segments: list[str],
    shared_drive: bool = False,
    cache: dict[tuple[str, str], str] | None = None,
) -> str:
    """Resolve (creating as needed) ``root/segments...`` and return the leaf id."""
    if not root_id:
        raise DriveError("GOOGLE_DRIVE_ROOT_FOLDER_ID is not set")

    cache = cache if cache is not None else {}
    parent = root_id
    for segment in segments:
        key = (parent, segment)
        if key in cache:
            parent = cache[key]
            continue
        found = find_child(service, parent, segment, shared_drive)
        if found is None:
            found = create_child(service, parent, segment, shared_drive)
        cache[key] = found
        parent = found
    return parent


def flyer_folder_path(company_name: str, when: date) -> list[str]:
    """``<Company>/Flyers/<YYYY>/<Month>/<MM-DD>``."""
    return [
        company_name,
        "Flyers",
        when.strftime("%Y"),
        when.strftime("%B"),
        when.strftime("%m-%d"),
    ]
