"""Weighted asset selection - never random.

The selector answers one question: given a campaign and a layout, which photo
gives the headline the best chance of being readable?
"""

from __future__ import annotations

from ..config import load_json_config
from ..logging_setup import get_logger
from ..models import Asset
from .catalog import AssetCatalog

log = get_logger(__name__)

# Where each layout puts its headline. Assets with negative space there score higher.
LAYOUT_TEXT_REGIONS: dict[str, list[str]] = {
    "hero-full": ["bottom", "bottom-left"],
    "banner-lower-third": ["top", "center"],
    "split-diagonal": ["top", "top-right"],
    "offer-badge": ["center"],
    "before-after": ["center"],
    "stat-stack": ["center", "top"],
}


def _weights() -> dict[str, float]:
    return load_json_config("scoring.json")["asset_weights"]


def _modifiers() -> dict:
    return load_json_config("scoring.json").get("asset_modifiers", {})


def allowed_stages(angle: str) -> tuple[set[str], bool]:
    """Which work states may illustrate this angle, and whether unclassified is ok.

    A flyer selling premium roofing must not show a worn-out roof. Stage policy
    lives in ``config/stage-policy.json`` so the rule is editable without code.
    """
    try:
        config = load_json_config("stage-policy.json")
    except Exception:
        return {"after", "neutral", "before", "during", ""}, True

    entry = config.get("policy", {}).get(angle)
    allow = set(entry["allow"]) if entry else set(config.get("default_allow", []))
    unclassified_ok = angle in config.get("unclassified", {}).get("allow_for_angles", [])
    return allow, unclassified_ok


def stage_permitted(asset: Asset, angle: str) -> bool:
    stages, unclassified_ok = allowed_stages(angle)
    stage = asset.provenance.stage
    if not stage:
        return unclassified_ok
    return stage in stages


def score_asset(
    asset: Asset,
    service: str,
    layout: str,
    recent_asset_ids: list[str],
) -> float:
    weights = _weights()

    if asset.service == service:
        service_score = 1.0
    elif service in asset.tags:
        service_score = 0.8
    elif asset.service == "general":
        service_score = 0.45
    else:
        service_score = 0.1

    wanted_regions = LAYOUT_TEXT_REGIONS.get(layout, ["center"])
    overlap = len(set(wanted_regions) & set(asset.clear_regions))
    space_score = min(overlap / max(len(wanted_regions), 1), 1.0)

    # Mid-tone images take an overlay best; blown-out or crushed ones fight the text.
    contrast_score = 1.0 - min(abs(asset.mean_luminance - 0.45) / 0.45, 1.0)

    total = (
        weights["service_match"] * service_score
        + weights["negative_space_fit"] * space_score
        + weights["contrast_headroom"] * contrast_score
    )

    modifiers = _modifiers()
    # Client photography beats stock.
    if asset.is_client_owned:
        total *= modifiers.get("client_owned_bonus", 1.25)
    # Provenance rank dominates: real client media outranks everything.
    total *= asset.provenance.rank / 100.0 if asset.provenance.rank else 0.05
    # Recency is multiplicative so it can outrank the client bonus. Running the
    # same photograph two days in a row is a worse outcome than using stock.
    if asset.id in recent_asset_ids:
        position = recent_asset_ids.index(asset.id)
        penalty = modifiers.get("recency_penalty_most_recent", 0.40)
        decay = modifiers.get("recency_penalty_decay", 0.12)
        total *= min(penalty + decay * position, 1.0)

    return round(total, 4)


def select_asset(
    catalog: AssetCatalog,
    client_id: str,
    service: str,
    layout: str,
    recent_asset_ids: list[str] | None = None,
    exclude: set[str] | None = None,
    allow_non_production: bool = False,
    angle: str = "",
) -> Asset | None:
    """Best asset for this campaign, or ``None`` when nothing is eligible.

    **Production gate.** By default only assets whose provenance is both a real
    production source type *and* explicitly approved are considered. A synthetic
    placeholder can never pass, so a generated cartoon cannot be presented to a
    homeowner as a photograph of their neighbour's roof.

    ``allow_non_production=True`` is the development/test escape hatch. It is
    never set by the production pipeline.

    A ``None`` return is not an error: the renderer falls back to a brand
    background, which is far better than a fake photograph.
    """
    pool = [a for a in catalog.for_client(client_id) if a.id not in (exclude or set())]
    if not pool:
        return None

    if not allow_non_production:
        eligible = [a for a in pool if a.production_eligible]
        blocked = len(pool) - len(eligible)
        if blocked:
            log.info(
                "Excluded %d non-production asset(s) (placeholder/unapproved/unknown provenance)",
                blocked,
            )
        pool = eligible
        if not pool:
            log.warning(
                "No production-eligible photography for %s/%s. Falling back to a brand "
                "background rather than using a placeholder.",
                client_id,
                service,
            )
            return None

    # A worn roof cannot illustrate premium roofing, and a finished roof cannot
    # illustrate storm damage. Filter to the work states this message allows.
    if angle:
        on_message = [a for a in pool if stage_permitted(a, angle)]
        rejected = len(pool) - len(on_message)
        if rejected:
            stages, unclassified_ok = allowed_stages(angle)
            log.info(
                "Excluded %d asset(s) whose work state does not suit a %r message (allowed: %s%s)",
                rejected,
                angle,
                ", ".join(sorted(stages)) or "none",
                ", unclassified" if unclassified_ok else "",
            )
        pool = on_message
        if not pool:
            log.warning(
                "No photograph matches a %r message for %s/%s. Using a brand "
                "background rather than a contradictory image.",
                angle,
                client_id,
                service,
            )
            return None

    recent = recent_asset_ids or []
    ranked = sorted(pool, key=lambda a: score_asset(a, service, layout, recent), reverse=True)
    best = ranked[0]
    log.debug(
        "Selected asset %s (score %.3f) for %s/%s",
        best.id,
        score_asset(best, service, layout, recent),
        service,
        layout,
    )
    return best


def select_pair(
    catalog: AssetCatalog,
    client_id: str,
    service: str,
    layout: str,
    recent_asset_ids: list[str] | None = None,
    allow_non_production: bool = False,
) -> tuple[Asset | None, Asset | None]:
    """Two distinct assets for a before/after layout.

    Strongly prefers a genuine pair from the *same* project. Pairing one
    house's "before" with a different house's "after" would present two homes
    as a single job, which is exactly the kind of dishonesty the design system
    forbids. Only when no real pair exists does it fall back to two distinct
    images, and the caller can then choose a different layout.
    """
    pool = [
        a for a in catalog.for_client(client_id) if allow_non_production or a.production_eligible
    ]

    by_project: dict[str, dict[str, Asset]] = {}
    for asset in pool:
        project = asset.provenance.project
        stage = asset.provenance.stage
        if project and stage in ("before", "after"):
            by_project.setdefault(project, {})[stage] = asset

    # Prefer a pair whose service also matches the campaign.
    matched = [
        (project, stages)
        for project, stages in by_project.items()
        if "before" in stages and "after" in stages
    ]
    for project, stages in sorted(matched, key=lambda item: item[1]["after"].service != service):
        log.info("Using a real before/after pair from project %r", project)
        return stages["before"], stages["after"]

    log.warning(
        "No matched before/after pair for %s/%s; falling back to two distinct images",
        client_id,
        service,
    )
    first = select_asset(
        catalog,
        client_id,
        service,
        layout,
        recent_asset_ids,
        allow_non_production=allow_non_production,
    )
    if first is None:
        return None, None
    second = select_asset(
        catalog,
        client_id,
        service,
        layout,
        recent_asset_ids,
        exclude={first.id},
        allow_non_production=allow_non_production,
    )
    return first, second
