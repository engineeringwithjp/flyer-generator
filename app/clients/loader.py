"""Load client profiles from ``clients/<slug>/client.json``.

Adding a client is a directory plus a JSON file - no code change.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ..config import get_settings
from ..errors import ClientError
from ..logging_setup import get_logger
from ..models import Client

log = get_logger(__name__)

TEMPLATE_SLUG = "_template"


def clients_dir() -> Path:
    return get_settings().paths.clients


def list_clients(include_disabled: bool = False) -> list[Client]:
    """Every valid client profile on disk, sorted by id."""
    found: list[Client] = []
    root = clients_dir()
    if not root.exists():
        return found
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        try:
            client = load_client(entry.name)
        except ClientError as exc:
            log.warning("Skipping client %s: %s", entry.name, exc)
            continue
        if client.enabled or include_disabled:
            found.append(client)
    return found


def load_client(slug: str) -> Client:
    path = clients_dir() / slug / "client.json"
    if not path.exists():
        available = (
            [p.name for p in clients_dir().iterdir() if p.is_dir()]
            if clients_dir().exists()
            else []
        )
        raise ClientError(
            f"No client profile at {path}. Available: {', '.join(sorted(available)) or 'none'}"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClientError(f"{path} is not valid JSON: {exc}") from exc

    raw.pop("$schema", None)
    raw.pop("$comment", None)

    try:
        client = Client.model_validate(raw)
    except ValidationError as exc:
        raise ClientError(f"{path} failed validation:\n{exc}") from exc

    if client.id != slug:
        raise ClientError(f"{path}: id {client.id!r} does not match folder name {slug!r}")
    return client


def client_root(slug: str) -> Path:
    return clients_dir() / slug


def resolve_client_path(client: Client, relative: str) -> Path | None:
    """Resolve a client-relative asset path (e.g. a logo) to an existing file."""
    if not relative:
        return None
    candidate = Path(relative)
    for base in (client_root(client.id), get_settings().paths.root):
        resolved = base / candidate if not candidate.is_absolute() else candidate
        if resolved.exists():
            return resolved
    return None
