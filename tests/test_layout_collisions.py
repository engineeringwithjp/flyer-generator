"""No layout may draw one block of copy on top of another.

Two layouts shipped with this bug - ``before-after`` printed the CTA button
over the support line, and ``banner-lower-third`` printed the bullets through
it. Both passed every check there was: the file was a valid image of the right
size with legible contrast, so the only way to see the problem was to look at
it. The renderer now records where each block of copy lands, and this sweeps
every layout against copy long enough to expose a bad vertical budget.
"""

from __future__ import annotations

import pytest

from app.models import CanvasSpec, FlyerCopy, FlyerSpecification, ImageSpec, LayoutSpec
from app.rendering.templates import LAYOUT_BUILDERS

LONG = FlyerCopy(
    eyebrow="BERGEN COUNTY ROOFING",
    headline="Thirty Years Up There. One Day Down Here.",
    support="Full tear-off, GAF Timberline HDZ, and a 50-year Master Elite warranty available.",
    bullets=[
        "Licensed & insured New Jersey contractor",
        "NJ HIC #13VH12314700",
        "GAF Master Elite contractor",
    ],
    cta="Book Your Roof Estimate",
    offer_badge="FREE ESTIMATE",
)
SHORT = FlyerCopy(
    eyebrow="ROOFING",
    headline="New Roof.",
    support="Done right.",
    bullets=["Licensed & insured"],
    cta="Call Us",
)


@pytest.mark.parametrize("layout", sorted(LAYOUT_BUILDERS))
@pytest.mark.parametrize("copy,label", [(LONG, "long"), (SHORT, "short")])
def test_no_layout_draws_copy_over_copy(repo, layout, copy, label):
    from app.clients.loader import load_client
    from app.config import get_settings
    from app.rendering.renderer import render_flyer, resolve_render_context

    settings = get_settings()
    client = load_client("testco")
    spec = FlyerSpecification(
        id=f"{layout}-{label}",
        client_id=client.id,
        campaign_id="roof-replacement",
        service="roofing",
        canvas=CanvasSpec(width=settings.output_width, height=settings.output_height),
        layout=LayoutSpec(name=layout),
        text=copy.model_copy(deep=True),
        image=ImageSpec(pair_confirmed=True),
        palette={
            "primary": "#14181C",
            "accent": "#DC1F26",
            "ink": "#14181C",
            "paper": "#FFFFFF",
            "on_image": "#FFFFFF",
        },
    )
    _, warnings = render_flyer(spec, resolve_render_context(client, {}))
    overlaps = [w for w in warnings if "overlap by" in w]
    assert not overlaps, f"{layout} ({label}): {'; '.join(overlaps)}"
