"""Tests for copywriting anti-AI rules and constraint enforcement."""

from src.core.copywriter import Copywriter


def test_copywriter_no_em_dashes(sample_client):
    cw = Copywriter(sample_client)
    copy = cw.generate_copy("Composite Siding", focus_topic="Built-in insulation")

    assert "—" not in copy.headline
    assert "--" not in copy.headline
    assert "—" not in copy.subheadline
    for b in copy.bullet_benefits:
        assert "—" not in b
        assert "--" not in b

def test_copywriter_no_emojis(sample_client):
    cw = Copywriter(sample_client)
    copy = cw.generate_copy("Roof Replacement")

    combined = f"{copy.headline} {copy.subheadline} {' '.join(copy.bullet_benefits)} {copy.cta_text}"
    for ch in combined:
        assert ord(ch) < 0x1F300 or ord(ch) > 0x1F6FF
