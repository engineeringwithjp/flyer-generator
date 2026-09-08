"""Standing instructions from the account owner, as checks rather than prose.

Everything here traces to something that was asked for once and must hold from
then on. They live apart from the generic QA in ``app/pipeline/validate.py``
because that module is client-neutral - it knows what a broken flyer looks
like, not what *this* account has decided is unacceptable.

Each rule records the instruction it came from, so a rule can be argued with
later instead of being quietly deleted because nobody remembers why it exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Client, FlyerSpecification, QAIssue, Severity


@dataclass(frozen=True)
class Rule:
    id: str
    instruction: str  # what was asked for, in the owner's words
    blocking: bool = True


RULES: tuple[Rule, ...] = (
    Rule("logo_on_every_flyer", "From now on always put the logo"),
    Rule(
        "retired_company_name",
        "avoid 'All Elite Construction Corp.' use 'All Elite Roofing & Siding'",
    ),
    Rule(
        "no_before_photo_on_finished_message",
        "some flyers with the old images of the home doesn't make sense in context",
    ),
    Rule(
        "real_photography_only", "recreates them using their own drone photos of client job sites"
    ),
    Rule(
        "copy_is_written_not_generic", "Be more creative with texts like a designer", blocking=False
    ),
    Rule("service_matches_the_business", "use All Elite Roofing & Siding for all future"),
    Rule(
        "before_after_pair_confirmed",
        "some flyers with the old images of the home doesn't make sense in context",
    ),
)

#: Names the business no longer trades under. Anything matching these must not
#: appear in copy - the company renamed and old collateral is being replaced.
RETIRED_NAMES = (
    "all elite construction corp",
    "all elite construction",
)

#: Phrasing that reads as a template rather than as marketing. Not fatal on its
#: own, but three of these in one flyer means the writer was not engaged.
GENERIC_PHRASES = (
    "what to know about",
    "available to",
    "guidance for",
    "services for",
    "solutions for",
    "your trusted",
    "quality workmanship",
    "we are committed",
    "contact us today for",
)


def _issue(check: str, severity: Severity, message: str, detail: str = "") -> QAIssue:
    return QAIssue(check=check, severity=severity, message=message, detail=detail)


def check(
    spec: FlyerSpecification,
    client: Client,
    asset_stage: str = "",
    logo_drawn: bool = True,
) -> list[QAIssue]:
    """Apply every house rule to one flyer."""
    issues: list[QAIssue] = []
    text = spec.text
    blob = " ".join(
        [text.eyebrow, text.headline, text.support, text.cta, *text.bullets, text.offer_badge]
    )
    lowered = blob.lower()

    # ---- the logo, on every flyer, without exception
    if not logo_drawn or spec.layout.logo_position == "none":
        issues.append(
            _issue(
                "logo_on_every_flyer",
                Severity.ERROR,
                "no logo on this flyer - every flyer carries the client mark",
            )
        )

    # ---- the company renamed; the old name must not ship
    for retired in RETIRED_NAMES:
        # The website domain still contains the old name and is correct as a
        # URL, so only prose occurrences count.
        prose = re.sub(r"\S+\.(com|net|org)\S*", " ", lowered)
        if retired in prose:
            issues.append(
                _issue(
                    "retired_company_name",
                    Severity.ERROR,
                    f"copy uses the retired name {retired!r}; the business is "
                    f"{client.company_name}",
                    blob,
                )
            )
            break

    # ---- a "before" photograph under finished-work messaging
    finished_language = any(
        phrase in lowered
        for phrase in ("completed", "finished", "done right", "final walkthrough", "after")
    )
    # A before/after layout is *supposed* to lead with the before shot; the
    # rule is about a lone "before" photo standing in for finished work.
    is_comparison = spec.layout.name == "before-after"
    if asset_stage == "before" and finished_language and not is_comparison:
        issues.append(
            _issue(
                "no_before_photo_on_finished_message",
                Severity.ERROR,
                "the photograph is a 'before' shot but the copy describes completed work",
            )
        )

    # ---- the trade this business is actually in
    trades = {s.lower() for s in client.services}
    if spec.service not in {"general", *trades}:
        issues.append(
            _issue(
                "service_matches_the_business",
                Severity.ERROR,
                f"flyer sells {spec.service!r}, which {client.company_name} does not offer",
            )
        )

    # ---- copy that reads as a template
    hits = [phrase for phrase in GENERIC_PHRASES if phrase in lowered]
    if hits:
        issues.append(
            _issue(
                "copy_is_written_not_generic",
                Severity.ERROR if len(hits) > 1 else Severity.WARNING,
                f"copy reads as filler: {', '.join(repr(h) for h in hits)}",
                blob,
            )
        )

    # ---- a headline that is only the campaign name is not a headline
    if text.headline.strip().lower() == spec.campaign_id.replace("-", " ").lower():
        issues.append(
            _issue(
                "copy_is_written_not_generic",
                Severity.ERROR,
                "the headline is just the campaign name",
                text.headline,
            )
        )

    # ---- the eyebrow is a second chance to say something, not an echo
    eyebrow = " ".join(text.eyebrow.lower().split())
    headline = " ".join(text.headline.lower().split())
    if eyebrow and headline.startswith(eyebrow):
        issues.append(
            _issue(
                "eyebrow_adds_something",
                Severity.WARNING,
                "the eyebrow just repeats the opening of the headline",
                f"{text.eyebrow!r} / {text.headline!r}",
            )
        )

    # ---- a before/after pair asserts two photographs are the same house
    if spec.layout.name == "before-after" and not spec.image.pair_confirmed:
        issues.append(
            _issue(
                "before_after_pair_confirmed",
                Severity.ERROR,
                "before/after pairing has not been confirmed by a person - a wrong pair "
                "presents two different houses as one job",
                f"{spec.image.asset_id} -> {spec.image.secondary_asset_id}",
            )
        )

    return issues
