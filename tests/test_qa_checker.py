"""Tests for automated QA checker and Human Design Test."""

from src.core.models import AssetMetadata, FlyerCopy, FlyerSpecification
from src.qa.checker import QAChecker
from src.renderer.engine import FlyerRenderer


def test_qa_checker_passes_clean_flyer(sample_client, tmp_path):
    renderer = FlyerRenderer()
    qa = QAChecker()
    out_file = str(tmp_path / "qa_pass.png")

    copy = FlyerCopy(
        tagline_badge="ROOFING",
        headline="YOUR ROOF DESERVES BETTER.",
        subheadline="Precision Roof Replacement Built to Endure",
        bullet_benefits=["Class A Fire Rating", "Impact Resistant"],
        cta_text="SCHEDULE FREE ESTIMATE",
        phone="(201) 755-4653",
        service_area="Northern New Jersey"
    )

    spec = FlyerSpecification(
        specification_id="qa_spec_pass",
        client=sample_client,
        archetype="hero_image",
        copy_content=copy,
        background_asset=AssetMetadata(asset_id="bg", category="roofing", file_path="", source="internal"),
        created_at="2026-09-05T00:00:00Z"
    )

    saved_path = renderer.render_flyer(spec, output_path=out_file)
    result = qa.evaluate(spec, saved_path)

    assert result.passed is True
    assert result.score >= 85
    assert len(result.violations) == 0

def test_qa_checker_fails_em_dash(sample_client, tmp_path):
    renderer = FlyerRenderer()
    qa = QAChecker()
    out_file = str(tmp_path / "qa_fail_dash.png")

    copy = FlyerCopy(
        tagline_badge="ROOFING",
        headline="YOUR ROOF DESERVES BETTER — CALL TODAY",  # Has em dash!
        subheadline="Precision Roof Replacement",
        bullet_benefits=["Class A Fire Rating"],
        cta_text="FREE ESTIMATE",
        phone="(201) 755-4653"
    )

    spec = FlyerSpecification(
        specification_id="qa_spec_fail_dash",
        client=sample_client,
        archetype="hero_image",
        copy_content=copy,
        background_asset=AssetMetadata(asset_id="bg", category="roofing", file_path="", source="internal"),
        created_at="2026-09-05T00:00:00Z"
    )

    saved_path = renderer.render_flyer(spec, output_path=out_file)
    result = qa.evaluate(spec, saved_path)

    assert result.passed is False
    assert any("em dash" in v for v in result.violations)
