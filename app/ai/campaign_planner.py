"""Decide which campaigns run today.

Claude gets the catalogue, the client profile and the recent history and picks
a varied, seasonally sensible batch. When Claude is unavailable the
deterministic planner below produces the same shape of plan using
least-recently-used rotation, so the pipeline never depends on the API to run.
"""

from __future__ import annotations

from datetime import date

from ..config import load_json_config
from ..logging_setup import get_logger
from ..models import Brief, Campaign, CampaignCatalog, CampaignPlan, Client, PlannedFlyer
from .claude_client import ClaudeClient, compact_json, get_claude
from .skill import system_prompt

log = get_logger(__name__)

LAYOUTS = [
    "hero-full",
    "banner-lower-third",
    "split-diagonal",
    "offer-badge",
    "before-after",
    "stat-stack",
]


def load_catalog() -> CampaignCatalog:
    raw = load_json_config("campaigns.json")
    raw.pop("$comment", None)
    return CampaignCatalog.model_validate(raw)


def season_for(when: date) -> str:
    return {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "fall",
        10: "fall",
        11: "fall",
    }[when.month]


def _plan_schema(count: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "strategy_note": {
                "type": "string",
                "description": "One sentence on why this mix suits today.",
            },
            "flyers": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                        "layout": {"type": "string", "enum": LAYOUTS},
                        "offer_id": {
                            "type": ["string", "null"],
                            "description": "Only an id present in the client's authorised offers, else null.",
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["campaign_id", "layout", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["flyers"],
        "additionalProperties": False,
    }


PROMPT = """Plan today's flyer batch.

DATE: {today}  ({weekday}, {season})
CLIENT PROFILE:
{client}

AUTHORISED OFFERS (the only offers copy may reference):
{offers}

ELIGIBLE CAMPAIGNS:
{campaigns}

ANGLE GUIDE:
{angles}

RECENT HISTORY (most recent first - avoid repeating these):
{history}

OPERATOR BRIEF FOR TODAY (overrides your judgement for flyer 1 where it is set):
{brief}

Choose exactly {count} campaigns.

Rules:
- Never repeat a campaign_id used in the last 10 days.
- Do not use the same layout twice in one batch, or the layout used yesterday.
- Vary the angle: pair a demand-capture flyer (offer/urgency/problem) with a
  trust or brand flyer. Two discount flyers in one day is a bad batch.
- Respect the season. A gutter-guard push in February is wasted.
- Only set offer_id when the campaign genuinely leads with an authorised offer.
- Only pick campaigns whose service the client actually offers.
"""


def plan_campaigns(
    client: Client,
    count: int,
    today: date,
    history: list[dict],
    forced_campaign: str | None = None,
    brief: Brief | None = None,
    claude: ClaudeClient | None = None,
) -> CampaignPlan:
    """Choose today's campaigns.

    A ``brief`` narrows the plan to what the operator actually cares about; the
    rest is inferred from the catalogue, the season and the history.
    """
    brief = brief or Brief()
    catalog = load_catalog()
    season = season_for(today)
    eligible = catalog.for_services(client.services)

    if not eligible:
        raise ValueError(
            f"No campaigns match client services {client.services!r}. "
            "Add services to client.json or campaigns to config/campaigns.json."
        )

    if forced_campaign:
        eligible = _apply_force(catalog, eligible, forced_campaign)

    claude = claude or get_claude()
    plan: CampaignPlan
    if claude.enabled:
        try:
            plan = _plan_with_claude(
                claude, client, count, today, season, eligible, catalog, history, brief
            )
        except Exception as exc:
            log.warning("Campaign planner falling back to rotation: %s", exc)
            plan = _plan_deterministic(client, count, today, season, eligible, history)
    else:
        plan = _plan_deterministic(client, count, today, season, eligible, history)

    return _apply_brief(plan, brief, client)


def _apply_brief(plan: CampaignPlan, brief: Brief, client: Client) -> CampaignPlan:
    """The operator's brief overrides the planner for the first flyer."""
    if brief.is_empty or not plan.flyers:
        return plan

    from ..design_system import archetype_for_layout, layout_for_archetype

    first = plan.flyers[0]
    if brief.message:
        first.primary_message = brief.message
    if brief.product_id and any(p.id == brief.product_id for p in client.products):
        first.product_id = brief.product_id
    if brief.archetype:
        layout = layout_for_archetype(brief.archetype)
        if layout:
            first.archetype = brief.archetype
            first.layout = layout
        else:
            log.warning("Unknown archetype %r - keeping the planned layout", brief.archetype)

    for flyer in plan.flyers:
        if not flyer.archetype:
            found = archetype_for_layout(flyer.layout)
            if found:
                flyer.archetype = found["id"]
    return plan


# --------------------------------------------------------------------- helpers


def _apply_force(catalog: CampaignCatalog, eligible: list[Campaign], forced: str) -> list[Campaign]:
    """`--campaign` accepts either a campaign id or a service name."""
    exact = catalog.by_id(forced)
    if exact:
        return [exact]
    by_service = [c for c in eligible if c.service == forced.lower()]
    if by_service:
        return by_service
    raise ValueError(
        f"Unknown campaign or service {forced!r}. "
        f"Try one of: {', '.join(sorted({c.service for c in eligible}))}"
    )


def _plan_with_claude(
    claude: ClaudeClient,
    client: Client,
    count: int,
    today: date,
    season: str,
    eligible: list[Campaign],
    catalog: CampaignCatalog,
    history: list[dict],
    brief: Brief,
) -> CampaignPlan:
    payload = claude.structured(
        system=system_prompt("planner", client.id),
        prompt=PROMPT.format(
            today=today.isoformat(),
            weekday=today.strftime("%A"),
            season=season,
            client=compact_json(
                {
                    "company": client.company_name,
                    "location": client.location,
                    "service_area": client.service_area,
                    "services": client.services,
                    "audience": client.target_audience,
                    "tone": client.tone,
                    "goal": client.primary_goal,
                    "proof_points": client.proof_points,
                }
            ),
            offers=compact_json([o.model_dump() for o in client.offers]) or "none",
            campaigns=compact_json(
                [
                    {
                        "id": c.id,
                        "name": c.name,
                        "service": c.service,
                        "angle": c.angle,
                        "objective": c.objective,
                        "in_season": c.in_season(season),
                        "preferred_layouts": c.preferred_layouts,
                    }
                    for c in eligible
                ]
            ),
            angles=compact_json(catalog.angles),
            history=compact_json(history[:20]) or "none",
            count=count,
            brief=compact_json(brief.model_dump()) if not brief.is_empty else "none - plan freely",
        ),
        tool_name="submit_campaign_plan",
        tool_description="Submit today's campaign plan for this client.",
        schema=_plan_schema(count),
        temperature=0.9,
        max_tokens=2048,
    )

    valid_offers = {o.id for o in client.offers}
    flyers: list[PlannedFlyer] = []
    for slot, item in enumerate(payload["flyers"], start=1):
        campaign = catalog.by_id(item["campaign_id"])
        if campaign is None:
            log.warning("Planner returned unknown campaign %s - substituting", item["campaign_id"])
            campaign = eligible[(slot - 1) % len(eligible)]
        offer_id = item.get("offer_id")
        if offer_id not in valid_offers:
            offer_id = None
        flyers.append(
            PlannedFlyer(
                slot=slot,
                campaign_id=campaign.id,
                service=campaign.service,
                angle=campaign.angle,
                layout=item.get("layout") or _default_layout(campaign),
                rationale=item.get("rationale", ""),
                offer_id=offer_id,
            )
        )

    return CampaignPlan(
        client_id=client.id,
        date=today.isoformat(),
        season=season,
        flyers=_dedupe_layouts(flyers),
        strategy_note=payload.get("strategy_note", ""),
    )


def _plan_deterministic(
    client: Client,
    count: int,
    today: date,
    season: str,
    eligible: list[Campaign],
    history: list[dict],
) -> CampaignPlan:
    """Least-recently-used rotation. No API required."""
    recent_ids = [entry.get("campaign") for entry in history]
    recent_layouts = [entry.get("layout") for entry in history[:2]]

    def staleness(campaign: Campaign) -> tuple[int, int, str]:
        try:
            last_used = recent_ids.index(campaign.id)
        except ValueError:
            last_used = 10_000
        return (-last_used, 0 if campaign.in_season(season) else 1, campaign.id)

    ordered = sorted(eligible, key=staleness)

    chosen: list[PlannedFlyer] = []
    used_angles: set[str] = set()
    for campaign in ordered:
        if len(chosen) >= count:
            break
        # Prefer a different angle for the second slot.
        if campaign.angle in used_angles and len(ordered) > count * 2:
            continue
        layout = _default_layout(campaign, avoid=recent_layouts)
        used_angles.add(campaign.angle)
        chosen.append(
            PlannedFlyer(
                slot=len(chosen) + 1,
                campaign_id=campaign.id,
                service=campaign.service,
                angle=campaign.angle,
                layout=layout,
                rationale="Least-recently-used rotation (deterministic planner).",
                offer_id=_default_offer(client, campaign),
            )
        )

    # Top up if the angle filter was too strict.
    for campaign in ordered:
        if len(chosen) >= count:
            break
        if any(c.campaign_id == campaign.id for c in chosen):
            continue
        chosen.append(
            PlannedFlyer(
                slot=len(chosen) + 1,
                campaign_id=campaign.id,
                service=campaign.service,
                angle=campaign.angle,
                layout=_default_layout(campaign, avoid=recent_layouts),
                rationale="Rotation top-up.",
                offer_id=_default_offer(client, campaign),
            )
        )

    return CampaignPlan(
        client_id=client.id,
        date=today.isoformat(),
        season=season,
        flyers=_dedupe_layouts(chosen),
        strategy_note="Deterministic rotation (Claude unavailable or disabled).",
    )


def _default_layout(campaign: Campaign, avoid: list | None = None) -> str:
    avoid = [a for a in (avoid or []) if a]
    for layout in campaign.preferred_layouts:
        if layout not in avoid:
            return layout
    if campaign.preferred_layouts:
        return campaign.preferred_layouts[0]
    return "banner-lower-third"


def _default_offer(client: Client, campaign: Campaign) -> str | None:
    if campaign.angle != "offer":
        return None
    for offer in client.offers:
        if not offer.services or campaign.service in offer.services or "general" in offer.services:
            return offer.id
    return None


def _dedupe_layouts(flyers: list[PlannedFlyer]) -> list[PlannedFlyer]:
    """Two flyers in one batch must not share a layout."""
    seen: set[str] = set()
    for flyer in flyers:
        if flyer.layout in seen:
            for candidate in LAYOUTS:
                if candidate not in seen:
                    flyer.layout = candidate
                    break
        seen.add(flyer.layout)
    return flyers
