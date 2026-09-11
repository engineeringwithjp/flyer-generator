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


def test_unapproved_materials_rejected(client):
    """Unapproved materials like ABC Pro Guard are strictly rejected in favor of GAF/ZIP System."""
    spec = _spec(client, text={"support": "Installed with ABC Pro Guard underlayment."})
    issues = check(spec, client)
    assert "no_unapproved_materials" in _errors(issues)


def test_before_photo_on_standard_layout_rejected(client):
    """Never use before photos unless the layout is explicitly a before-after comparison."""
    spec = _spec(client, image={"asset_id": "projects/closter/before/dji_001.jpg"})
    issues = check(spec, client)
    assert "no_before_photo_without_comparison" in _errors(issues)


def test_before_photo_allowed_on_comparison_layout(client):
    """Before photos are permitted on confirmed before-after comparison layouts."""
    spec = _spec(
        client,
        layout={"name": "before-after"},
        image={
            "asset_id": "projects/closter/before/dji_001.jpg",
            "secondary_asset_id": "projects/closter/after/dji_002.jpg",
            "pair_confirmed": True,
        },
    )
    issues = check(spec, client)
    assert "no_before_photo_without_comparison" not in _errors(issues)

