"""Quality control: the gate that stops a bad flyer reaching a client."""

from __future__ import annotations

import pytest
from PIL import Image

from app.copy_rules import RISKY_CLAIM, clip_words, filler_hits, strip_ai_punctuation
from app.models import CanvasSpec, FlyerCopy, FlyerSpecification, ImageSpec, LayoutSpec, Severity
from app.pipeline.validate import qa_flyer, validate_environment
from app.rendering.export import export_flyer
from app.rendering.renderer import render_flyer, resolve_render_context


def _spec(**copy_overrides) -> FlyerSpecification:
    copy = {
        "eyebrow": "Bergen County",
        "headline": "Your Roof Deserves Better",
        "support": "Roof replacement for Bergen County homeowners",
        "bullets": [],
        "cta": "Get A Free Estimate",
    }
    copy.update(copy_overrides)
    return FlyerSpecification(
        id="qa_test",
        client_id="testco",
        campaign_id="roof-replacement",
        service="roofing",
        canvas=CanvasSpec(),
        layout=LayoutSpec(name="hero-full"),
        image=ImageSpec(),
        text=FlyerCopy(**copy),
        palette={
            "primary": "#12243A",
            "accent": "#E0A62F",
            "ink": "#111111",
            "paper": "#FFFFFF",
            "on_image": "#FFFFFF",
        },
    )


@pytest.fixture()
def rendered(repo, client, tmp_path):
    def _render(spec):
        image, warnings = render_flyer(spec, resolve_render_context(client, {}))
        path = export_flyer(image, tmp_path / f"{spec.id}.png", "PNG")
        return path, warnings

    return _render


def _checks(result):
    return {i.check for i in result.issues} | {i.check for i in result.warnings}


# ------------------------------------------------------------------ baseline


def test_a_clean_flyer_passes(repo, client, rendered):
    spec = _spec()
    path, warnings = rendered(spec)
    result = qa_flyer(path, spec, client, warnings)
    assert result.passed, [str(i) for i in result.issues]
    assert result.score >= 90


# ----------------------------------------------------------------- technical


def test_a_missing_file_is_an_error(repo, client, tmp_path):
    result = qa_flyer(tmp_path / "nope.png", _spec(), client)
    assert not result.passed and "file_exists" in _checks(result)


def test_an_empty_file_is_an_error(repo, client, tmp_path):
    path = tmp_path / "empty.png"
    path.touch()
    result = qa_flyer(path, _spec(), client)
    assert not result.passed and "file_size" in _checks(result)


def test_a_non_image_is_an_error(repo, client, tmp_path):
    path = tmp_path / "fake.png"
    path.write_bytes(b"x" * 30000)
    result = qa_flyer(path, _spec(), client)
    assert not result.passed and "image_readable" in _checks(result)


def test_wrong_dimensions_are_an_error(repo, client, tmp_path):
    path = tmp_path / "small.png"
    Image.new("RGB", (500, 500), (30, 40, 50)).save(path)
    result = qa_flyer(path, _spec(), client)
    assert not result.passed and "dimensions" in _checks(result)


def test_a_uniform_flyer_is_flagged_as_a_failed_render(repo, client, tmp_path):
    path = tmp_path / "blank.png"
    Image.new("RGB", (1080, 1350), (128, 128, 128)).save(path)
    result = qa_flyer(path, _spec(), client)
    assert not result.passed and "blank_output" in _checks(result)


# ---------------------------------------------------------------------- copy


def test_placeholder_text_is_an_error(repo, client, rendered):
    spec = _spec(headline="Lorem Ipsum Roofing")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "placeholder_text" in _checks(result)


def test_a_template_token_is_an_error(repo, client, rendered):
    spec = _spec(support="Serving {{county}} homeowners")
    path, _ = rendered(spec)
    assert not qa_flyer(path, spec, client).passed


def test_an_em_dash_is_an_error(repo, client, rendered):
    spec = _spec(support="Roof replacement — done properly")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "ai_punctuation" in _checks(result)


def test_an_en_dash_is_an_error(repo, client, rendered):
    spec = _spec(headline="Roofing – Done Right")
    path, _ = rendered(spec)
    assert "ai_punctuation" in _checks(qa_flyer(path, spec, client))


def test_an_emoji_is_an_error(repo, client, rendered):
    spec = _spec(cta="Get A Quote \U0001f680")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "emoji" in _checks(result)


def test_one_filler_phrase_warns(repo, client, rendered):
    spec = _spec(support="Elevate your home this season")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert "ai_filler" in _checks(result)


def test_several_filler_phrases_fail(repo, client, rendered):
    spec = _spec(
        headline="Unlock Your Home",
        support="Seamless, world-class service",
    )
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "ai_filler" in _checks(result)


def test_duplicate_words_warn(repo, client, rendered):
    spec = _spec(support="Roof roof replacement for homeowners")
    path, _ = rendered(spec)
    assert "duplicate_words" in _checks(qa_flyer(path, spec, client))


def test_a_risky_insurance_claim_is_an_error(repo, client, rendered):
    spec = _spec(headline="Get A Free Roof", support="Insurance will pay for it")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "risky_claim" in _checks(result)


def test_free_roof_inspection_is_legitimate(repo, client, rendered):
    """Regression: an honest offer must not trip the storm-chaser filter."""
    spec = _spec(headline="Free Roof Inspection")
    path, _ = rendered(spec)
    assert "risky_claim" not in _checks(qa_flyer(path, spec, client))


def test_an_unverified_number_warns(repo, client, rendered):
    spec = _spec(bullets=["Over 9,000 roofs installed"])
    path, _ = rendered(spec)
    assert "unverified_number" in _checks(qa_flyer(path, spec, client))


def test_a_verified_number_does_not_warn(repo, client, rendered):
    spec = _spec(bullets=["NJ HIC #13VH00000000"])
    path, _ = rendered(spec)
    assert "unverified_number" not in _checks(qa_flyer(path, spec, client))


def test_an_unauthorised_offer_is_an_error(repo, client, rendered):
    spec = _spec(offer_badge="50% Off Everything")
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "unauthorised_offer" in _checks(result)


def test_an_authorised_offer_passes(repo, client, rendered):
    spec = _spec(offer_badge="Free Roof Inspection")
    path, _ = rendered(spec)
    assert "unauthorised_offer" not in _checks(qa_flyer(path, spec, client))


def test_too_much_text_warns(repo, client, rendered):
    spec = _spec(
        headline="Roof Replacement Services Available",
        support="We provide complete roofing services for homeowners across the region today",
        bullets=["Licensed and insured across the state", "Free written estimates provided"],
    )
    path, _ = rendered(spec)
    assert "text_volume" in _checks(qa_flyer(path, spec, client))


def test_a_spec_for_another_client_is_an_error(repo, client, rendered):
    spec = _spec()
    spec.client_id = "someone-else"
    path, _ = rendered(spec)
    result = qa_flyer(path, spec, client)
    assert not result.passed and "client_match" in _checks(result)


# ------------------------------------------------------------- copy_rules API


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Free Roof Inspection", False),
        ("Free Roof Estimate", False),
        ("Get a free roof", True),
        ("Guaranteed approval", True),
        ("No cost to you", True),
    ],
)
def test_risky_claim_regex(text, expected):
    assert bool(RISKY_CLAIM.search(text)) is expected


def test_strip_ai_punctuation():
    assert "—" not in strip_ai_punctuation("a — b")


def test_clip_words_never_cuts_mid_word():
    assert clip_words("Licensed and insured New Jersey contractor", 20) == "Licensed and insured"


def test_clip_words_leaves_short_text_alone():
    assert clip_words("Short", 40) == "Short"


def test_filler_hits_are_detected():
    assert "cutting-edge" in filler_hits("Our cutting-edge process")


# ------------------------------------------------------------- environment


def test_environment_validation_passes_without_credentials(repo):
    result = validate_environment()
    assert result.passed, [str(i) for i in result.issues]
    assert any(i.check == "ANTHROPIC_API_KEY" for i in result.warnings)


def test_a_bad_canvas_size_fails_validation(repo, monkeypatch):
    from app.config import reset_settings_cache

    monkeypatch.setenv("OUTPUT_WIDTH", "10")
    reset_settings_cache()
    assert not validate_environment().passed


def test_a_bad_schedule_time_fails_validation(repo, monkeypatch):
    from app.config import reset_settings_cache

    monkeypatch.setenv("SCHEDULE_TIME", "ten oclock")
    reset_settings_cache()
    result = validate_environment()
    assert not result.passed
    assert any(i.check == "SCHEDULE_TIME" for i in result.issues)


def test_qa_result_severity_scoring():
    from app.models import QAIssue, QAResult

    result = QAResult.from_issues(
        [
            QAIssue(check="a", severity=Severity.ERROR, message="bad"),
            QAIssue(check="b", severity=Severity.WARNING, message="meh"),
        ]
    )
    assert not result.passed
    assert result.score == 70
