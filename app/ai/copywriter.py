"""Marketing copy generation.

Hard constraints live in the JSON Schema (character budgets) and in
``copywriting-rules.md`` (voice, forbidden claims). Anything Claude returns is
re-validated by ``FlyerCopy`` before it can reach the renderer.
"""

from __future__ import annotations

import hashlib
import re

BANNED_PHRASES = ("elevate", "unleash", "tapestry", "game-changer", "delve")


def _clip_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:- ")
    return clipped or text[:max_chars]


def _strip_ai_punctuation(text: str) -> str:
    return text.replace("—", " - ").replace("–", " - ")

from ..logging_setup import get_logger
from ..models import Campaign, Client, FlyerCopy, PlannedFlyer
from .claude_client import ClaudeClient, compact_json, get_claude
from .skill import system_prompt

log = get_logger(__name__)

#: Longest a proof point may be and still fit a bullet line at flyer scale.
BULLET_LIMIT = 44

COPY_SCHEMA = {
    "type": "object",
    "properties": {
        "eyebrow": {
            "type": "string",
            "maxLength": 34,
            "description": "Small label above the headline, e.g. the service name or service area. May be empty.",
        },
        "headline": {
            "type": "string",
            "minLength": 3,
            "maxLength": 54,
            "description": "3-8 words. The whole message. Must survive being scaled to 180px wide.",
        },
        "support": {
            "type": "string",
            "maxLength": 110,
            "description": "One supporting sentence. No exclamation marks.",
        },
        "bullets": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 44},
            "description": "Optional proof points. Only facts from the client profile.",
        },
        "cta": {
            "type": "string",
            "minLength": 3,
            "maxLength": 32,
            "description": "One action. Imperative. e.g. 'Get Your Free Estimate'.",
        },
        "offer_badge": {
            "type": "string",
            "maxLength": 26,
            "description": "Short badge text. Only when an authorised offer was supplied, else empty.",
        },
        "disclaimer": {
            "type": "string",
            "maxLength": 120,
            "description": "Offer fine print, verbatim from the authorised offer. Else empty.",
        },
    },
    "required": ["headline", "cta"],
    "additionalProperties": False,
}

PROMPT = """Write the copy for one flyer.

CAMPAIGN: {campaign_name}  (id: {campaign_id})
SERVICE:  {service}
ANGLE:    {angle} - {angle_guide}
LAYOUT:   {layout} (text density: {density})
ARCHETYPE:{archetype}

THE ONE THING THIS FLYER IS ABOUT:
{primary_message}

FEATURED PRODUCT (a material option this contractor installs - never the advertiser):
{product}

CLIENT:
{client}

VERIFIED PROOF POINTS - the only facts you may state as claims:
{proof_points}

AUTHORISED OFFER FOR THIS FLYER:
{offer}

FORBIDDEN:
{forbidden}

HEADLINES USED RECENTLY - do not repeat or lightly reword these:
{recent_headlines}

Write for a homeowner scrolling a phone. Every word earns its place.

Write like a branding agency, not like an AI. Specifically:
- NO em dashes or en dashes. Use a comma, a full stop or a colon.
- NO emoji of any kind.
- NO generic marketing filler ("unlock", "elevate your", "seamless",
  "cutting-edge", "world-class", "look no further", "peace of mind you deserve",
  "take your home to the next level", "when it comes to", "rest assured").
- NO hedging, NO throat-clearing, NO restating the campaign name as a sentence.
Plain, confident, corporate. The kind of line a good agency would put on a
billboard.
Respect the character budgets exactly - the renderer will not shrink text to
rescue an overlong headline.

If no offer is supplied, leave `offer_badge` and `disclaimer` empty.
Never invent statistics, warranties, licence numbers, awards, review counts or
years in business. If it is not in the proof points, it does not exist.
"""


def write_copy(
    client: Client,
    planned: PlannedFlyer,
    campaign: Campaign,
    angle_guide: str,
    text_density: str,
    recent_headlines: list[str],
    claude: ClaudeClient | None = None,
) -> FlyerCopy:
    offer = next((o for o in client.offers if o.id == planned.offer_id), None)
    product = next((p for p in client.products if p.id == planned.product_id), None)
    claude = claude or get_claude()

    if claude.enabled:
        try:
            payload = claude.structured(
                system=system_prompt("copywriter", client.id),
                prompt=PROMPT.format(
                    campaign_name=campaign.name,
                    campaign_id=campaign.id,
                    service=planned.service,
                    angle=planned.angle,
                    angle_guide=angle_guide,
                    layout=planned.layout,
                    density=text_density,
                    archetype=planned.archetype or "not specified",
                    primary_message=planned.primary_message
                    or "not specified - choose the strongest angle for this campaign",
                    product=compact_json(product.model_dump()) if product else "none",
                    client=compact_json(
                        {
                            "company": client.company_name,
                            "location": client.location,
                            "service_area": client.service_area,
                            "audience": client.target_audience,
                            "tone": client.tone,
                            "goal": client.primary_goal,
                        }
                    ),
                    proof_points=compact_json(client.proof_points) or "none - state no claims",
                    offer=compact_json(offer.model_dump()) if offer else "none",
                    forbidden=compact_json(client.forbidden_claims)
                    or "none beyond the standard rules",
                    recent_headlines=compact_json(recent_headlines[:12]) or "none",
                ),
                tool_name="submit_flyer_copy",
                tool_description="Submit the finished marketing copy for one flyer.",
                schema=COPY_SCHEMA,
                temperature=0.95,
                max_tokens=1200,
            )
            copy = FlyerCopy.model_validate(_sanitise(payload, offer is not None))
            _warn_on_filler(copy)
            return copy
        except Exception as exc:
            log.warning("Copywriter falling back to templates: %s", exc)

    return _fallback_copy(client, planned, campaign, offer, product)


# --------------------------------------------------------------------- helpers


def _sanitise(payload: dict, offer_allowed: bool) -> dict:
    payload = dict(payload)
    payload.setdefault("eyebrow", "")
    payload.setdefault("support", "")
    payload.setdefault("bullets", [])
    payload.setdefault("offer_badge", "")
    payload.setdefault("disclaimer", "")
    if not offer_allowed:
        # Belt and braces: no authorised offer means no offer language, ever.
        payload["offer_badge"] = ""
        payload["disclaimer"] = ""
    for key in ("eyebrow", "headline", "support", "cta", "offer_badge", "disclaimer"):
        if payload.get(key):
            payload[key] = _strip_ai_punctuation(str(payload[key]))
    payload["bullets"] = [_strip_ai_punctuation(b) for b in payload.get("bullets", [])]
    payload["headline"] = re.sub(r"\s+", " ", payload["headline"]).strip()
    payload["cta"] = re.sub(r"\s+", " ", payload["cta"]).strip().rstrip(".")
    return payload


def _warn_on_filler(copy: FlyerCopy) -> None:
    blob = " ".join([copy.eyebrow, copy.headline, copy.support, copy.cta]).lower()
    hits = [phrase for phrase in BANNED_PHRASES if phrase in blob]
    if hits:
        log.warning("Copy contains generic marketing filler: %s", ", ".join(hits))


def _copy_bank() -> dict:
    """Written copy keyed by campaign, from ``config/copy-bank.json``."""
    from ..config import load_json_config

    try:
        return load_json_config("copy-bank.json")
    except Exception as exc:  # a malformed bank must not stop a run
        log.warning("copy-bank.json unavailable (%s); using the generic writer", exc)
        return {}


def _pick(options: list[str], seed: str) -> str:
    """Choose one variant, deterministically but differently per flyer.

    Hashing the seed rather than cycling an index means two flyers in the same
    batch get different lines, the same flyer re-rendered gets the same line,
    and the choice does not drift as the bank grows.
    """
    if not options:
        return ""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return options[digest[0] % len(options)]


def _banked_copy(client, planned, campaign) -> dict[str, str]:
    """The written lines for this campaign, falling back to its angle."""
    bank = _copy_bank()
    entry = bank.get("by_campaign", {}).get(campaign.id) or {}
    angle_entry = bank.get("by_angle", {}).get(planned.angle) or {}

    seed_base = f"{campaign.id}|{planned.slot}|{planned.layout}"
    chosen: dict[str, str] = {}
    for field in ("eyebrow", "headline", "support", "cta"):
        options = entry.get(field) or angle_entry.get(field) or []
        chosen[field] = _pick(list(options), f"{seed_base}|{field}")
    return chosen


def _fallback_copy(client, planned, campaign, offer, product=None) -> FlyerCopy:
    """Copy used when Claude is unavailable - which is every scheduled run
    unless an API key is configured.

    Two sources, in order. ``config/copy-bank.json`` holds lines written for
    each campaign; anything it does not cover falls through to the generic
    constructions below. Neither may assert something the client profile does
    not already contain - the bank is written copy, not a licence to invent.
    """
    area = client.service_area[0] if client.service_area else client.location
    service_word = campaign.service.replace("-", " ").title()
    # "Gutters" and "Windows" are plural nouns; "Roofing" and "Siding" are not.
    # Without this, the fallback writer produces "Is Your Gutters Failing?".
    is_plural = service_word.endswith("s") and not service_word.endswith("ss")
    verb_be = "Are" if is_plural else "Is"

    # Deliberately plain and honest. These run only when Claude is unavailable,
    # so they must never overreach - and they must never read as a placeholder.
    headlines = {
        "upgrade": f"{service_word} Done Right",
        "problem": f"{verb_be} Your {service_word} Failing?",
        "urgency": f"Fast {service_word} Service",
        "offer": campaign.name,
        "proof": f"See Our {service_word} Work",
        "education": f"What To Know About {service_word}",
        "emotional": "Protect What Matters Most",
        "premium": f"Premium {service_word}",
        # Only safe because these three words are asserted in proof_points;
        # the QA gate re-checks it against the client profile regardless.
        "trust": "Licensed, Insured, Local",
    }
    headline = _clip_words(headlines.get(planned.angle, f"{service_word} Services"), 54)
    if planned.primary_message:
        # The operator's brief wins over the generic angle headline.
        headline = _clip_words(planned.primary_message.strip().title(), 54)

    # Vary the supporting line by angle so a week of offline runs is not
    # six copies of the same sentence.
    if product:
        support = f"{product.name}, installed by {client.company_name}"
    else:
        where = f"{area} homeowners" if area else "New Jersey homeowners"
        # Every line here states only who is served and what the trade is.
        # No response times, no tenure, no offers: the fallback writer has no
        # licence to make a claim the client profile does not already contain.
        support = {
            "upgrade": f"{service_word} replacement for {where}",
            "problem": f"{service_word} inspection and repair for {where}",
            "urgency": f"{service_word} repair for {where}",
            "offer": f"Available to {where}",
            "proof": f"{service_word} projects for {where}",
            "education": f"{service_word} guidance for {where}",
            "emotional": f"{service_word} for {where}",
            "premium": f"{service_word} for {where}",
            "trust": f"{service_word} for {where}",
        }.get(planned.angle, f"{service_word} for {where}")

    cta_map = {
        "phone_call": "Call Us Today",
        "lead_generation": "Get A Free Estimate",
        "trust": "Learn More",
        "brand": "See Our Work",
    }
    cta = cta_map.get(client.primary_goal, "Get A Free Estimate")

    banked = _banked_copy(client, planned, campaign)
    # The operator's own brief still outranks the bank.
    if banked.get("headline") and not planned.primary_message:
        headline = _clip_words(banked["headline"], 60)
    if banked.get("support"):
        support = banked["support"]
    if banked.get("cta"):
        cta = banked["cta"]
    eyebrow = banked.get("eyebrow") or area or client.location or ""

    # Rotate which proof points appear, so four flyers in a batch do not carry
    # the same three lines. The set is fixed; the window into it moves.
    #
    # A proof point longer than the bullet budget is skipped, not clipped. A
    # clipped bullet reads as a bug - "A dedicated project manager as your
    # single" - and it is better to show two whole claims than three broken
    # ones.
    points = [p for p in (client.proof_points or []) if len(p) <= BULLET_LIMIT]
    bullets: list[str] = []
    if points:
        offset = (planned.slot - 1) * 3 % len(points)
        bullets = [points[(offset + i) % len(points)] for i in range(min(3, len(points)))]

    return FlyerCopy(
        eyebrow=_clip_words(eyebrow, 34),
        headline=headline,
        support=_clip_words(support, 110),
        bullets=bullets,
        cta=cta,
        offer_badge=_clip_words(offer.text, 26) if offer else "",
        disclaimer=_clip_words(offer.fine_print, 120) if offer else "",
    )
