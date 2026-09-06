"""Reference-library storage and weighted selection.

The library is the design-inspiration corpus. Selection is scored, never
random, and ``rejected`` references are hard-excluded rather than penalised.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .config import get_settings, load_json_config
from .errors import ReferenceError
from .logging_setup import get_logger
from .models import Client, ReferenceImage, ReferenceIndex, ReferenceStatus

log = get_logger(__name__)


# --------------------------------------------------------------------- store


def load_index() -> ReferenceIndex:
    path = get_settings().paths.reference_index
    if not path.exists():
        return ReferenceIndex()
    try:
        return ReferenceIndex.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReferenceError(f"Reference index at {path} is corrupt: {exc}") from exc


def save_index(index: ReferenceIndex) -> Path:
    path = get_settings().paths.reference_index
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def sidecar_path(reference: ReferenceImage) -> Path:
    return get_settings().paths.root / Path(reference.path).with_suffix(".json")


def write_sidecar(reference: ReferenceImage) -> Path:
    path = sidecar_path(reference)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reference.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def status_dir(status: ReferenceStatus, category: str) -> Path:
    settings = get_settings()
    base = {
        ReferenceStatus.APPROVED: settings.paths.reference_approved,
        ReferenceStatus.EXPERIMENTAL: settings.paths.reference_experimental,
        ReferenceStatus.REJECTED: settings.paths.reference_rejected,
        ReferenceStatus.INBOX: settings.paths.reference_inbox,
    }[status]
    return base / category


def promote(reference_id: str, status: ReferenceStatus) -> ReferenceImage:
    """Move a reference between approved / experimental / rejected."""
    index = load_index()
    reference = index.by_id(reference_id)
    if reference is None:
        raise ReferenceError(f"Unknown reference id {reference_id!r}")

    settings = get_settings()
    old_path = settings.paths.root / reference.path
    old_sidecar = old_path.with_suffix(".json")

    target_dir = status_dir(status, reference.category)
    target_dir.mkdir(parents=True, exist_ok=True)
    new_path = target_dir / old_path.name

    if old_path.exists() and old_path.resolve() != new_path.resolve():
        shutil.move(str(old_path), str(new_path))
        if old_sidecar.exists():
            shutil.move(str(old_sidecar), str(new_path.with_suffix(".json")))

    reference.status = status
    reference.path = str(new_path.relative_to(settings.paths.root))
    index.upsert(reference)
    save_index(index)
    write_sidecar(reference)
    log.info("Reference %s -> %s", reference_id, status)
    return reference


def record_outcome(reference_ids: list[str], approved: bool) -> None:
    """Feed the approval/rejection signal back into reference scoring."""
    if not reference_ids:
        return
    index = load_index()
    for ref_id in reference_ids:
        reference = index.by_id(ref_id)
        if reference is None:
            continue
        reference.times_used += 1
        if approved:
            reference.approvals += 1
        else:
            reference.rejections += 1
    save_index(index)


# ----------------------------------------------------------------- selection


def _weights() -> tuple[dict, dict, dict]:
    """(weights, status multipliers, diversity settings) from scoring.json."""
    config = load_json_config("scoring.json")
    return config["weights"], config["status_multipliers"], config["diversity"]


def score_reference(
    reference: ReferenceImage,
    service: str,
    campaign_id: str,
    layout: str,
    client: Client,
    recent_reference_ids: list[str],
) -> float:
    weights, multipliers, diversity = _weights()

    multiplier = multipliers.get(reference.status.value, 0.0)
    if multiplier == 0.0:
        return 0.0

    if reference.category == service:
        service_score = 1.0
    elif reference.category == "general":
        service_score = 0.55
    else:
        service_score = 0.15

    if layout in reference.suggested_layouts:
        style_score = 1.0
    elif reference.suggested_layouts:
        style_score = 0.4
    else:
        style_score = 0.5
    if reference.style in client.preferred_reference_styles:
        style_score = min(style_score + 0.25, 1.0)

    campaign_score = 1.0 if campaign_id in reference.recommended_campaigns else 0.35

    preference_score = 1.0 if reference.style in client.preferred_reference_styles else 0.5

    total = (
        weights["service_relevance"] * service_score
        + weights["style_relevance"] * style_score
        + weights["campaign_relevance"] * campaign_score
        + weights["historical_performance"] * reference.performance
        + weights["client_preference"] * preference_score
    ) * multiplier

    if reference.id in recent_reference_ids:
        total *= 1.0 - diversity["reference_reuse_penalty"]

    return round(total, 4)


def select_reference(
    service: str,
    campaign_id: str,
    layout: str,
    client: Client,
    recent_reference_ids: list[str] | None = None,
    index: ReferenceIndex | None = None,
) -> ReferenceImage | None:
    """Highest-scoring usable reference, or ``None`` when the library is empty.

    ``None`` is a normal state on a fresh repository - the design director falls
    back to the client's brand and the layout defaults.
    """
    index = index or load_index()
    candidates = index.usable()
    if not candidates:
        return None

    recent = recent_reference_ids or []
    ranked = sorted(
        candidates,
        key=lambda r: score_reference(r, service, campaign_id, layout, client, recent),
        reverse=True,
    )
    best = ranked[0]
    score = score_reference(best, service, campaign_id, layout, client, recent)
    if score <= 0:
        return None
    log.info("Selected reference %s (%s, score %.3f)", best.id, best.style, score)
    return best


def summarise_library() -> dict[str, int]:
    index = load_index()
    summary: dict[str, int] = {"total": len(index.references)}
    for reference in index.references:
        summary[reference.status.value] = summary.get(reference.status.value, 0) + 1
    return summary
