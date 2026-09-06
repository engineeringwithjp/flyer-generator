"""Reference-image ingestion.

Drop a flyer you like into ``references/inbox/`` and run
``flyer ingest-reference``. The image is validated, analysed by Claude vision,
given structured metadata, filed under ``references/experimental/<category>/``
and added to the index. You promote it to ``approved/`` when you are happy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import references as reference_lib
from ..ai.campaign_planner import load_catalog
from ..ai.reference_analyzer import analyze_reference
from ..assets.image_utils import SUPPORTED_SUFFIXES, ensure_readable, file_sha256, load_rgb
from ..config import get_settings
from ..errors import ReferenceError
from ..logging_setup import get_logger
from ..models import ReferenceImage, ReferenceStatus

log = get_logger(__name__)


def ingest_reference(
    image_path: Path,
    status: ReferenceStatus = ReferenceStatus.EXPERIMENTAL,
    move: bool = True,
    force: bool = False,
) -> ReferenceImage:
    """Analyse and file one reference image. Returns the stored record."""
    settings = get_settings()
    image_path = image_path.resolve()
    ensure_readable(image_path)

    index = reference_lib.load_index()
    checksum = file_sha256(image_path)

    existing = next((r for r in index.references if r.sha256 == checksum), None)
    if existing and not force:
        log.info(
            "Reference %s is already in the library as %s (%s) - skipping",
            image_path.name,
            existing.id,
            existing.status,
        )
        return existing

    campaign_ids = [c.id for c in load_catalog().campaigns]
    analysis = analyze_reference(image_path, campaign_ids)

    with load_rgb(image_path) as image:
        width, height = image.size

    reference_id = existing.id if existing else index.next_id()
    category = analysis.get("category", "general")

    target_dir = reference_lib.status_dir(status, category)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_path(target_dir / _safe_name(reference_id, image_path))

    if move:
        shutil.move(str(image_path), str(target_path))
    else:
        shutil.copy2(str(image_path), str(target_path))

    reference = ReferenceImage(
        id=reference_id,
        filename=image_path.name,
        path=str(target_path.relative_to(settings.paths.root)),
        status=status,
        sha256=checksum,
        width=width,
        height=height,
        analyzed_by=settings.anthropic_vision_model,
        **{k: v for k, v in analysis.items() if k in ReferenceImage.model_fields},
    )

    index.upsert(reference)
    reference_lib.save_index(index)
    reference_lib.write_sidecar(reference)

    log.info(
        "Ingested %s -> %s (%s / %s / %s)",
        image_path.name,
        reference.id,
        reference.category,
        reference.style,
        reference.status,
    )
    return reference


def ingest_directory(
    directory: Path | None = None,
    status: ReferenceStatus = ReferenceStatus.EXPERIMENTAL,
    move: bool = True,
) -> list[ReferenceImage]:
    """Ingest every image in a directory (defaults to ``references/inbox``)."""
    settings = get_settings()
    directory = (directory or settings.paths.reference_inbox).resolve()
    if not directory.exists():
        raise ReferenceError(f"Inbox directory not found: {directory}")

    images = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not images:
        log.info("No images to ingest in %s", directory)
        return []

    log.info("Ingesting %d reference image(s) from %s", len(images), directory)
    ingested: list[ReferenceImage] = []
    for path in images:
        try:
            ingested.append(ingest_reference(path, status=status, move=move))
        except Exception as exc:
            log.error("Could not ingest %s: %s", path.name, exc)
    return ingested


def _safe_name(reference_id: str, original: Path) -> str:
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in original.stem.lower()).strip(
        "-"
    )[:48]
    return f"{reference_id}-{stem or 'reference'}{original.suffix.lower()}"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for counter in range(2, 100):
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ReferenceError(f"Could not find a free filename near {path}")
