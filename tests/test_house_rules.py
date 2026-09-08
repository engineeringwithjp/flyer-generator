"""The account owner's standing instructions, as tests.

Each of these corresponds to something that was asked for once and has to keep
holding. If one of them starts failing, a flyer that the owner has already
rejected is about to ship again.
"""

from __future__ import annotations

import pytest

from app.house_rules import RULES, check
from app.models import Severity


@pytest.fixture()
def client(repo):
    from app.clients.loader import load_client

    return load_client("testco")


def _spec(client, **overrides):
    from app.models import FlyerCopy, FlyerSpecification, ImageSpec, LayoutSpec

    text = FlyerCopy(
        eyebrow="ROOFING",
        headline="A Roof Built To Last",
        support="Full tear-off and rebuild by a licensed crew.",
        cta="Get A Free Estimate",
        bullets=["Licensed & insured"],
    )
    spec = FlyerSpecification(
        id="t1",
        client_id=client.id,
        campaign_id="roof-replacement",
        service="roofing",
        layout=LayoutSpec(name="hero-full"),
        image=ImageSpec(asset_id="a1"),
        text=text,
    )
    for key, value in overrides.items():
        if key == "text":
            for field, val in value.items():
                setattr(spec.text, field, val)
        elif key == "layout":
            for field, val in value.items():
                setattr(spec.layout, field, val)
        elif key == "image":
            for field, val in value.items():
                setattr(spec.image, field, val)
        else:
            setattr(spec, key, value)
    return spec


def _errors(issues):
    return {i.check for i in issues if i.severity is Severity.ERROR}


def test_every_rule_records_the_instruction_it_came_from():
    """A rule nobody can trace gets deleted the first time it is inconvenient."""
    for rule in RULES:
        assert rule.instruction.strip(), f"{rule.id} has no recorded instruction"


def test_a_flyer_without_the_logo_is_blocked(client):
    """ "From now on always put the logo"."""
    issues = check(_spec(client), client, logo_drawn=False)
    assert "logo_on_every_flyer" in _errors(issues)


def test_logo_position_none_is_also_blocked(client):
    issues = check(_spec(client, layout={"logo_position": "none"}), client)
    assert "logo_on_every_flyer" in _errors(issues)


def test_a_clean_flyer_passes(client):
    assert _errors(check(_spec(client), client)) == set()


def test_a_before_photo_under_finished_language_is_blocked(client):
    """ "some flyers with the old images of the home doesn't make sense"."""
    spec = _spec(client, text={"headline": "Completed Last Week"})
    assert "no_before_photo_on_finished_message" in _errors(
        check(spec, client, asset_stage="before")
    )


def test_a_before_photo_is_fine_on_a_before_after_layout(client):
    """The comparison layout is supposed to lead with the before shot."""
    spec = _spec(
        client,
        layout={"name": "before-after"},
        text={"headline": "Completed Last Week"},
        image={"pair_confirmed": True},
    )
    assert "no_before_photo_on_finished_message" not in _errors(
        check(spec, client, asset_stage="before")
    )


def test_an_unconfirmed_before_after_pair_is_blocked(client):
    """Matching folder names have already produced two different houses."""
    spec = _spec(client, layout={"name": "before-after"})
    assert "before_after_pair_confirmed" in _errors(check(spec, client))


def test_filler_copy_is_blocked(client):
    """ "Be more creative with texts like a designer"."""
    spec = _spec(
        client,
        text={
            "headline": "What To Know About Roofing",
            "support": "Roofing guidance for local homeowners",
        },
    )
    assert "copy_is_written_not_generic" in _errors(check(spec, client))


def test_a_headline_that_is_only_the_campaign_name_is_blocked(client):
    spec = _spec(client, text={"headline": "Roof Replacement"})
    assert "copy_is_written_not_generic" in _errors(check(spec, client))


def test_a_service_the_business_does_not_offer_is_blocked(client):
    spec = _spec(client, service="plumbing")
    assert "service_matches_the_business" in _errors(check(spec, client))
