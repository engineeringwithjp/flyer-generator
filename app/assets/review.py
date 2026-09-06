"""Promote reviewed media into the production library.

The one human step the provenance system deliberately requires. Extracted
frames and raw drone stills are real, but nothing reaches a client flyer until
somebody has looked at it and said yes.

    flyer assets --review              what is waiting
    flyer assets --promote <id> ...    approve specific assets
    flyer assets --promote-top 8       approve the highest-scoring candidates
    flyer assets --reject <id> ...     never offer these again
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import get_settings
from ..errors import AssetError
from ..logging_setup import get_logger
from ..models import ApprovalStatus, Asset, SourceType
from .catalog import AssetCatalog, save_asset_index

log = get_logger(__name__)

# Synthetic media can never be promoted, whatever the operator types.
PROMOTABLE = frozenset(
    {
        SourceType.CLIENT_PHOTO,
        SourceType.CLIENT_DRONE,
        SourceType.CLIENT_VIDEO_FRAME,
        SourceType.INTERNAL_BACKGROUND,
        SourceType.STOCK,
    }
)


def pending(catalog: AssetCatalog, client_id: str | None = None) -> list[Asset]:
    """Real media awaiting review, best candidates first."""
    assets = catalog.index.assets
    if client_id:
        assets = [a for a in assets if a.client_id == client_id]
    waiting = [
        a
        for a in assets
        if a.provenance.source_type in PROMOTABLE
        and a.provenance.approval_status is ApprovalStatus.UNAPPROVED
    ]
    return sorted(waiting, key=lambda a: a.quality_score, reverse=True)


def set_stage(catalog: AssetCatalog, asset_ids: list[str], stage: str) -> list[Asset]:
    """Record what work state an image shows.

    Without this a photograph can illustrate any message, so a worn roof can end
    up on a flyer selling premium roofing. Stage is the gate that prevents it.
    """
    valid = {"before", "during", "after", "neutral", ""}
    if stage not in valid:
        raise AssetError(f"stage must be one of {sorted(valid - {''})}, got {stage!r}")

    updated: list[Asset] = []
    for asset_id in asset_ids:
        asset = catalog.index.by_id(asset_id)
        if asset is None:
            raise AssetError(f"Unknown asset id: {asset_id}")
        asset.provenance.stage = stage  # type: ignore[assignment]
        catalog.index.upsert(asset)
        _persist_sidecar(asset)
        updated.append(asset)
        log.info("%s -> stage %s", asset.id, stage or "unclassified")
    save_asset_index(catalog.index)
    return updated


def _persist_sidecar(asset: Asset) -> None:
    """Write the stage next to the file so a reindex does not lose it."""
    settings = get_settings()
    path = (settings.paths.root / asset.path).with_suffix(".json")
    payload: dict = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.setdefault("provenance", {})["stage"] = asset.provenance.stage
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        log.warning("Could not write sidecar for %s: %s", asset.id, exc)


def unclassified(catalog: AssetCatalog, client_id: str | None = None) -> list[Asset]:
    """Production assets with no work state recorded."""
    assets = catalog.index.assets
    if client_id:
        assets = [a for a in assets if a.client_id == client_id]
    return [
        a for a in assets if a.production_eligible and not a.provenance.stage and not a.is_synthetic
    ]


def promote(catalog: AssetCatalog, asset_ids: list[str], move: bool = True) -> list[Asset]:
    """Approve assets and move them into ``assets/approved/``."""
    settings = get_settings()
    promoted: list[Asset] = []

    for asset_id in asset_ids:
        asset = catalog.index.by_id(asset_id)
        if asset is None:
            raise AssetError(f"Unknown asset id: {asset_id}")
        if asset.provenance.source_type not in PROMOTABLE:
            raise AssetError(
                f"{asset_id} is {asset.provenance.source_type.value} and can never be "
                "promoted to production."
            )

        if move and "/raw/" in asset.path.replace("\\", "/"):
            asset.path = _move_into_approved(settings.paths.root, asset)

        asset.provenance.approval_status = ApprovalStatus.APPROVED
        asset.provenance.verified_by = "human-review"
        catalog.index.upsert(asset)
        promoted.append(asset)
        log.info("Promoted %s -> production eligible", asset.id)

    save_asset_index(catalog.index)
    return promoted


def reject(catalog: AssetCatalog, asset_ids: list[str]) -> list[Asset]:
    """Mark assets rejected so the selector never offers them again."""
    rejected: list[Asset] = []
    for asset_id in asset_ids:
        asset = catalog.index.by_id(asset_id)
        if asset is None:
            raise AssetError(f"Unknown asset id: {asset_id}")
        asset.provenance.approval_status = ApprovalStatus.REJECTED
        asset.provenance.verified_by = "human-review"
        catalog.index.upsert(asset)
        rejected.append(asset)
        log.info("Rejected %s", asset.id)
    save_asset_index(catalog.index)
    return rejected


def _move_into_approved(root: Path, asset: Asset) -> str:
    """Relocate from ``assets/raw/**`` to ``assets/approved/``.

    Keeping approved media in one flat folder is what makes the library easy to
    look through, and it keeps the folder convention and the metadata agreeing.
    """
    source = root / asset.path
    if not source.exists():
        raise AssetError(f"Asset file is missing: {source}")

    client_root = source
    while client_root.parent.name != "assets" and client_root.parent != client_root:
        client_root = client_root.parent
    approved_dir = client_root.parent / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    target = approved_dir / source.name
    counter = 2
    while target.exists():
        target = approved_dir / f"{source.stem}-{counter}{source.suffix}"
        counter += 1

    shutil.move(str(source), str(target))
    sidecar = source.with_suffix(".json")
    if sidecar.exists():
        _merge_sidecar(sidecar, target.with_suffix(".json"))
        sidecar.unlink(missing_ok=True)

    return str(target.relative_to(root))


def _merge_sidecar(source: Path, target: Path) -> None:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    payload.setdefault("provenance", {})["approval_status"] = "approved"
    payload["provenance"]["verified_by"] = "human-review"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
