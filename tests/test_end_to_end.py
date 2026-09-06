"""End-to-end integration test for the flyer generation pipeline."""

from scripts.generate_flyers import generate_daily_flyers


def test_full_pipeline_run():
    records = generate_daily_flyers(
        client_id="all-elite",
        count=2,
        campaign_name="Composite Siding",
        focus_topic="Built-in insulation",
        cta_override="Free Estimate",
        upload_drive=True
    )
    assert len(records) == 2
    for r in records:
        assert r.client_id == "all-elite"
        assert r.qa_score >= 85
        assert r.output_path.endswith(".png")
        assert r.drive_file_id is not None
