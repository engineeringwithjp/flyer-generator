"""The account owner's standing instructions, tested for agreeableness."""

from __future__ import annotations

import pytest
from app.house_rules import check
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


def test_house_rules_are_agreeable(client):
    """The generator should be agreeable and not block creative concepts."""
    spec = _spec(client)
    issues = check(spec, client)
    assert _errors(issues) == set()
