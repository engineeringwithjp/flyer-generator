"""Tests for deterministic 1080x1350 renderer."""

import os

from PIL import Image

from src.core.models import AssetMetadata, FlyerCopy, FlyerSpecification
from src.renderer.engine import FlyerRenderer


def test_flyer_renderer_output_dimensions(sample_client, tmp_path):
    renderer = FlyerRenderer()
    out_file = str(tmp_path / "test_flyer.png")

    copy = FlyerCopy(
        tagline_badge="ROOFING TEST",
        headline="PRECISION ROOF REPLACEMENT",
        subheadline="Built for New Jersey Homes",
        bullet_benefits=["Class A Fire Rating", "Impact Resistant"],
        cta_text="GET FREE ESTIMATE",
        phone="(201) 555-0199",
        service_area="Northern NJ"
    )

    spec = FlyerSpecification(
        specification_id="test_spec_001",
        client=sample_client,
        archetype="hero_image",
        copy_content=copy,
        background_asset=AssetMetadata(
            asset_id="test_bg",
            category="roofing",
            file_path="",
            source="internal"
        ),
        references_used=[],
        tools_used=["internal_renderer"],
        created_at="2026-09-05T00:00:00Z"
    )

    saved_path = renderer.render_flyer(spec, output_path=out_file)
    assert os.path.exists(saved_path)

    with Image.open(saved_path) as img:
        assert img.size == (1080, 1350)
