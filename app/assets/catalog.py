"""Scan the photo libraries into a persisted index.

Two libraries feed the catalogue:

* ``assets/**``                  - the shared construction photography library
* ``clients/<slug>/assets/**``   - that client's own approved photography

Client-owned assets always outrank the shared library during selection.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from ..config import get_settings
from ..logging_setup import get_logger
from ..models import Asset, AssetIndex, FocalPoint
from .image_utils import SUPPORTED_SUFFIXES, analyse_image
from .metadata import (
    derive_client_id,
    derive_provenance,
    derive_service_from_path,
    derive_tags_from_path,
    load_sidecar,
)

log = get_logger(__name__)


def _iter_images(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        # Only skip dot-directories *inside* the library. Checking the absolute
        # path would exclude everything whenever the repo itself lives under a
        # dotted parent (a git worktree under .claude/, for example).
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        yield path


def _asset_id(relative: Path) -> str:
    """Stable, human-readable id derived from the path."""
    return str(relative.with_suffix("")).replace("/", ":").replace(" ", "-").lower()


def build_asset_index(deep: bool = True) -> AssetIndex:
    """Rebuild the asset index from disk.

    ``deep=False`` skips Pillow analysis (fast; used by ``validate``).
    """
    settings = get_settings()
    root = settings.paths.root
    index = AssetIndex()

    roots = [settings.paths.assets, settings.paths.clients]
    for library in roots:
        for path in _iter_images(library):
            relative = path.relative_to(root)
            # Logos are branding, not photography - excluded from selection.
            if "logo" in relative.parts:
                continue
            record: dict = {
                "id": _asset_id(relative),
                "path": str(relative),
                "client_id": derive_client_id(path),
                "service": derive_service_from_path(path),
                "tags": derive_tags_from_path(path),
                "provenance": derive_provenance(path),
            }
            if deep:
                try:
                    analysis = analyse_image(path)
                except Exception as exc:
                    log.warning("Skipping unreadable asset %s: %s", relative, exc)
                    continue
                record.update(analysis)
            record.update(load_sidecar(path))
            if isinstance(record.get("focal"), dict):
                record["focal"] = FocalPoint.model_validate(record["focal"])
            index.upsert(Asset.model_validate(record))

    log.info("Catalogued %d asset(s)", len(index.assets))
    return index


def load_asset_index() -> AssetIndex:
    path = get_settings().paths.asset_index
    if not path.exists():
        return AssetIndex()
    try:
        return AssetIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Asset index at %s is unreadable (%s); rebuilding", path, exc)
        return AssetIndex()


def save_asset_index(index: AssetIndex) -> Path:
    path = get_settings().paths.asset_index
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def refresh_asset_index(deep: bool = True) -> AssetIndex:
    """Rebuild from disk while preserving usage counters from the old index."""
    previous = load_asset_index()
    fresh = build_asset_index(deep=deep)
    for asset in fresh.assets:
        old = previous.by_id(asset.id)
        if old:
            asset.times_used = old.times_used
            asset.last_used = old.last_used
            asset.added_at = old.added_at
    save_asset_index(fresh)
    return fresh


class AssetCatalog:
    """Query layer over the asset index."""

    def __init__(self, index: AssetIndex) -> None:
        self.index = index

    @classmethod
    def load(cls, refresh: bool = False, deep: bool = True) -> AssetCatalog:
        index = refresh_asset_index(deep=deep) if refresh else load_asset_index()
        if not index.assets and not refresh:
            index = refresh_asset_index(deep=deep)
        return cls(index)

    @property
    def is_empty(self) -> bool:
        return not self.index.assets

    def for_client(self, client_id: str) -> list[Asset]:
        """Client-owned assets first, then the shared library."""
        owned = [a for a in self.index.assets if a.client_id == client_id]
        shared = [a for a in self.index.assets if a.client_id is None]
        return owned + shared

    def for_service(self, client_id: str, service: str) -> list[Asset]:
        pool = self.for_client(client_id)
        exact = [a for a in pool if a.service == service]
        tagged = [a for a in pool if a not in exact and service in a.tags]
        general = [a for a in pool if a.service == "general" and a not in exact and a not in tagged]
        return exact + tagged + general

    def inventory_summary(self, client_id: str) -> list[dict]:
        """Compact inventory handed to Claude so it only picks assets that exist."""
        summary = []
        for asset in self.for_client(client_id):
            summary.append(
                {
                    "asset_id": asset.id,
                    "service": asset.service,
                    "tags": asset.tags[:6],
                    "clear_regions": asset.clear_regions,
                    "luminance": round(asset.mean_luminance, 2),
                    "orientation": "portrait" if asset.is_portrait else "landscape",
                    "client_owned": asset.is_client_owned,
                }
            )
        return summary

    def mark_used(self, asset_id: str, when: str) -> None:
        asset = self.index.by_id(asset_id)
        if asset:
            asset.times_used += 1
            asset.last_used = when
            save_asset_index(self.index)


def write_asset_index_json(index: AssetIndex, path: Path) -> None:
    path.write_text(json.dumps(index.model_dump(), indent=2) + "\n", encoding="utf-8")
