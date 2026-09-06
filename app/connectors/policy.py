"""The decision engine: which connectors, if any, earn their place today.

The operator does not choose tools. This does, from the state of the internal
libraries, and it records why. The bias is strongly toward doing nothing:
an external call has to beat what the repository already has.

    client photos  >  approved flyers  >  design system  >  reference library
                   >  figma / canva / mobbin  >  unsplash
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..config import load_json_config
from ..logging_setup import get_logger
from .base import ConnectorStatus
from .registry import all_connectors, available_names

log = get_logger(__name__)


class ToolDecision(BaseModel):
    """Structured, loggable answer to 'which tools and why'."""

    need_stock_photo: bool = False
    need_external_reference: bool = False
    use_unsplash: bool = False
    use_mobbin: bool = False
    use_figma: bool = False
    use_canva: bool = False
    reasons: list[str] = Field(default_factory=list)
    skipped: dict[str, str] = Field(default_factory=dict)
    overrides_applied: list[str] = Field(default_factory=list)

    @property
    def tools_used(self) -> list[str]:
        return [
            name
            for name, on in (
                ("unsplash", self.use_unsplash),
                ("mobbin", self.use_mobbin),
                ("figma", self.use_figma),
                ("canva", self.use_canva),
            )
            if on
        ]

    @property
    def any_external(self) -> bool:
        return bool(self.tools_used)

    def explain(self) -> str:
        if not self.any_external:
            return "Internal sources only: " + (
                "; ".join(self.reasons) or "nothing external was needed."
            )
        return f"Using {', '.join(self.tools_used)}. " + "; ".join(self.reasons)


class ConnectorOverrides(BaseModel):
    """Explicit operator instructions. These beat the automatic decision."""

    internal_only: bool = False
    no_stock_photography: bool = False
    force: list[str] = Field(default_factory=list, description="Connector names to force on")
    forbid: list[str] = Field(default_factory=list, description="Connector names to force off")

    @property
    def is_empty(self) -> bool:
        return not (self.internal_only or self.no_stock_photography or self.force or self.forbid)


def decide(
    *,
    has_suitable_asset: bool,
    internal_reference_count: int,
    best_reference_score: float,
    days_since_direction_changed: int | None = None,
    editable_deliverable_requested: bool = False,
    building_template_system: bool = False,
    overrides: ConnectorOverrides | None = None,
    today: date | None = None,
) -> ToolDecision:
    """Decide which connectors to use for one flyer."""
    overrides = overrides or ConnectorOverrides()
    settings = load_json_config("connectors.json")
    thresholds = settings["thresholds"]
    defaults = settings["defaults"]

    decision = ToolDecision()
    reachable = set(available_names())

    def skip(name: str, why: str) -> None:
        decision.skipped[name] = why

    # ---- Hard operator overrides first -------------------------------------
    if overrides.internal_only:
        decision.overrides_applied.append("internal-only")
        decision.reasons.append("Operator requested internal sources only.")
        for name in all_connectors():
            skip(name, "operator requested internal sources only")
        return decision

    # ---- Photography -------------------------------------------------------
    if has_suitable_asset:
        decision.reasons.append("A suitable internal photograph exists, so no stock search.")
        skip("unsplash", "a suitable client or internal photograph already exists")
    elif overrides.no_stock_photography or not defaults.get("allow_stock_photography", True):
        decision.reasons.append(
            "No internal photograph, but stock photography is disallowed; "
            "a procedural brand background will be used."
        )
        skip("unsplash", "stock photography is disallowed")
        if overrides.no_stock_photography:
            decision.overrides_applied.append("no-stock-photography")
    else:
        decision.need_stock_photo = True
        if "unsplash" in reachable:
            decision.use_unsplash = True
            decision.reasons.append("No internal photograph for this campaign; sourcing one.")
        else:
            skip("unsplash", _unreachable_reason("unsplash"))
            decision.reasons.append(
                "No internal photograph and Unsplash is unavailable; "
                "falling back to a procedural brand background."
            )

    # ---- Design inspiration ------------------------------------------------
    thin_library = internal_reference_count < thresholds["min_internal_references_before_external"]
    weak_match = best_reference_score < thresholds["reference_score_floor"]
    stale = (
        days_since_direction_changed is not None
        and days_since_direction_changed > thresholds["stale_direction_after_days"]
    )

    if not (thin_library or weak_match or stale):
        decision.reasons.append(
            f"The internal reference library is sufficient "
            f"({internal_reference_count} references, best score {best_reference_score:.2f})."
        )
        skip("mobbin", "the internal reference library already covers this campaign")
    else:
        decision.need_external_reference = True
        why = (
            "the internal reference library is thin"
            if thin_library
            else "no internal reference matches this campaign well"
            if weak_match
            else "the visual direction has not changed in a while"
        )
        if "mobbin" in reachable:
            decision.use_mobbin = True
            decision.reasons.append(f"Seeking pattern inspiration because {why}.")
        else:
            skip("mobbin", _unreachable_reason("mobbin"))
            decision.reasons.append(
                f"Would seek external inspiration ({why}) but Mobbin is unavailable; "
                "using the design system defaults."
            )

    # ---- Editable deliverables --------------------------------------------
    if editable_deliverable_requested:
        if "canva" in reachable:
            decision.use_canva = True
            decision.reasons.append("An editable client deliverable was requested.")
        elif "figma" in reachable:
            decision.use_figma = True
            decision.reasons.append(
                "An editable deliverable was requested; Canva is unavailable, using Figma."
            )
        else:
            skip("canva", _unreachable_reason("canva"))
            skip("figma", _unreachable_reason("figma"))
            decision.reasons.append(
                "An editable deliverable was requested but neither Canva nor Figma is "
                "available; delivering a rendered PNG instead."
            )
    else:
        skip("canva", "deterministic rendering already produces the deliverable")

    if building_template_system:
        if "figma" in reachable:
            decision.use_figma = True
            decision.reasons.append("Building or revising the master layout system.")
        else:
            skip("figma", _unreachable_reason("figma"))
    elif "figma" not in decision.skipped and not decision.use_figma:
        skip("figma", "no template work is required for a routine daily flyer")

    # ---- Explicit force / forbid ------------------------------------------
    for name in overrides.forbid:
        setattr(decision, f"use_{name}", False)
        skip(name, "operator forbade this connector")
        decision.overrides_applied.append(f"forbid:{name}")

    for name in overrides.force:
        if not hasattr(decision, f"use_{name}"):
            log.warning("Unknown connector in override: %s", name)
            continue
        decision.overrides_applied.append(f"force:{name}")
        if name in reachable:
            setattr(decision, f"use_{name}", True)
            decision.skipped.pop(name, None)
            decision.reasons.append(f"Operator explicitly requested {name}.")
        else:
            skip(name, f"operator requested it but {_unreachable_reason(name)}")
            decision.reasons.append(
                f"Operator requested {name} but it is not available; using internal sources."
            )

    return decision


def _unreachable_reason(name: str) -> str:
    connector = all_connectors().get(name)
    if connector is None:
        return "no adapter is registered"
    status = connector.probe()
    return {
        ConnectorStatus.CONFIGURATION_REQUIRED: "it needs authorisation",
        ConnectorStatus.NOT_INSTALLED: "it is not connected in this environment",
        ConnectorStatus.DISABLED: "it is disabled in config/connectors.json",
        ConnectorStatus.FAILED: "it failed on the last call",
    }.get(status, "it is unavailable")


def parse_overrides(text: str | None) -> ConnectorOverrides:
    """Turn a plain-language instruction into overrides.

    Supports the phrasings the operator actually uses:
    "use canva", "no stock photography", "internal references only".
    """
    if not text:
        return ConnectorOverrides()
    lowered = text.lower()
    overrides = ConnectorOverrides()

    if any(
        phrase in lowered
        for phrase in (
            "internal only",
            "internal references only",
            "internal assets only",
            "no external",
            "don't use external",
            "do not use external",
        )
    ):
        overrides.internal_only = True

    if any(
        phrase in lowered
        for phrase in ("no stock", "don't use stock", "do not use stock", "no unsplash")
    ):
        overrides.no_stock_photography = True
        overrides.forbid.append("unsplash")

    for name in all_connectors():
        if f"use {name}" in lowered or f"use the {name}" in lowered:
            overrides.force.append(name)
        forbidden = (
            f"don't use {name}" in lowered
            or f"do not use {name}" in lowered
            or f"no {name}" in lowered
        )
        if forbidden and name not in overrides.forbid:
            overrides.forbid.append(name)

    overrides.force = [n for n in overrides.force if n not in overrides.forbid]
    return overrides
