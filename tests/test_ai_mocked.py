"""Claude integration, with the API mocked. No unit test may hit the network."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.ai.claude_client import ClaudeClient
from app.ai.copywriter import write_copy
from app.ai.design_director import direct_design
from app.ai.qa_agent import vision_qa
from app.ai.reference_analyzer import analyze_reference
from app.errors import AIError, ConfigurationError
from app.models import CanvasSpec, FlyerCopy, PlannedFlyer


def _tool_response(payload: dict, name: str):
    block = SimpleNamespace(type="tool_use", name=name, input=payload)
    return SimpleNamespace(
        content=[block],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


@pytest.fixture()
def online(repo, monkeypatch):
    from app.config import reset_settings_cache

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-not-real")
    monkeypatch.setenv("FLYER_OFFLINE", "0")
    reset_settings_cache()
    return ClaudeClient()


# ----------------------------------------------------------------- client


def test_claude_is_disabled_without_a_key(repo):
    assert ClaudeClient().enabled is False


def test_require_claude_explains_how_to_fix_it(repo, monkeypatch):
    from app.config import reset_settings_cache

    monkeypatch.setenv("FLYER_OFFLINE", "0")
    reset_settings_cache()
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        ClaudeClient().settings.require_claude()


def test_offline_mode_reports_itself_clearly(repo):
    with pytest.raises(ConfigurationError, match="FLYER_OFFLINE"):
        ClaudeClient().settings.require_claude()


def test_offline_flag_disables_claude_even_with_a_key(repo, monkeypatch):
    from app.config import reset_settings_cache

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("FLYER_OFFLINE", "1")
    reset_settings_cache()
    assert ClaudeClient().enabled is False


def test_structured_returns_the_tool_input(online, monkeypatch):
    monkeypatch.setattr(online, "_call", lambda **kw: _tool_response({"ok": True}, "t"))
    assert online.structured(
        system="s", prompt="p", tool_name="t", tool_description="d", schema={}
    ) == {"ok": True}


def test_a_missing_tool_call_raises(online, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hi")], stop_reason="end_turn", usage=None
        ),
    )
    with pytest.raises(AIError, match="did not call the required tool"):
        online.structured(system="s", prompt="p", tool_name="t", tool_description="d", schema={})


def test_transient_failures_are_retried(online, monkeypatch):
    class RateLimitError(Exception):
        status_code = 429

    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("slow down")
        return _tool_response({"ok": True}, "t")

    online._client = SimpleNamespace(messages=SimpleNamespace(create=flaky))
    monkeypatch.setattr("time.sleep", lambda *_: None)
    assert online._call(model="m", max_tokens=10, messages=[])
    assert calls["n"] == 3


def test_a_permanent_failure_raises_after_the_retries(online, monkeypatch):
    class BadRequest(Exception):
        status_code = 400

    online._client = SimpleNamespace(
        messages=SimpleNamespace(create=MagicMock(side_effect=BadRequest("nope")))
    )
    with pytest.raises(AIError, match="failed after"):
        online._call(model="m", max_tokens=10, messages=[])


def test_oversized_images_are_downscaled(online, repo):
    big = repo / "assets" / "roofing" / "huge.jpg"
    Image.new("RGB", (5000, 4000), (120, 130, 140)).save(big, quality=100)
    block = online._image_block(big)
    assert block["source"]["media_type"] in {"image/jpeg", "image/png"}
    assert len(block["source"]["data"]) > 100


def test_an_unknown_image_type_is_rejected(online, repo):
    bad = repo / "assets" / "roofing" / "thing.tiff"
    bad.write_bytes(b"x")
    with pytest.raises(AIError, match="Unsupported image type"):
        online._image_block(bad)


# --------------------------------------------------------------- copywriter


def _planned(**kw):
    payload = {
        "slot": 1,
        "campaign_id": "roof-replacement",
        "service": "roofing",
        "angle": "upgrade",
        "layout": "hero-full",
    }
    payload.update(kw)
    return PlannedFlyer(**payload)


def test_copywriter_uses_claude_when_available(online, client, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "headline": "Your Roof, Sorted",
                "cta": "Get A Free Estimate",
                "support": "Roof replacement for Bergen County homeowners",
            },
            "submit_flyer_copy",
        ),
    )
    campaign = next(
        c
        for c in __import__("app.ai.campaign_planner", fromlist=["x"]).load_catalog().campaigns
        if c.id == "roof-replacement"
    )
    copy = write_copy(client, _planned(), campaign, "", "low", [], claude=online)
    assert copy.headline == "Your Roof, Sorted"


def test_copywriter_strips_em_dashes_from_the_model_output(online, client, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {"headline": "Roofing — Done Right", "cta": "Call Us"}, "submit_flyer_copy"
        ),
    )
    campaign = next(
        c
        for c in __import__("app.ai.campaign_planner", fromlist=["x"]).load_catalog().campaigns
        if c.id == "roof-replacement"
    )
    copy = write_copy(client, _planned(), campaign, "", "low", [], claude=online)
    assert "—" not in copy.headline


def test_copywriter_drops_an_offer_that_was_not_authorised(online, client, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {"headline": "Roof Replacement", "cta": "Call", "offer_badge": "70% OFF"},
            "submit_flyer_copy",
        ),
    )
    campaign = next(
        c
        for c in __import__("app.ai.campaign_planner", fromlist=["x"]).load_catalog().campaigns
        if c.id == "roof-replacement"
    )
    copy = write_copy(client, _planned(offer_id=None), campaign, "", "low", [], claude=online)
    assert copy.offer_badge == ""


def test_copywriter_falls_back_when_claude_errors(online, client, monkeypatch):
    monkeypatch.setattr(online, "_call", MagicMock(side_effect=AIError("down")))
    campaign = next(
        c
        for c in __import__("app.ai.campaign_planner", fromlist=["x"]).load_catalog().campaigns
        if c.id == "roof-replacement"
    )
    copy = write_copy(client, _planned(), campaign, "", "low", [], claude=online)
    assert copy.headline and copy.cta


# ------------------------------------------------------------ design director


def test_director_never_invents_an_asset_id(online, client, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "style": "premium-modern",
                "overlay": "dark_gradient",
                "overlay_strength": 0.6,
                "crop": "focal",
                "text_align": "left",
                "logo_position": "top-left",
                "asset_id": "hallucinated-asset",
            },
            "submit_design_specification",
        ),
    )
    spec = direct_design(
        client,
        _planned(),
        FlyerCopy(headline="Test Headline", cta="Call Now"),
        None,
        None,
        None,
        "",
        CanvasSpec(),
        "flyer_1",
        claude=online,
    )
    assert spec.image.asset_id is None


def test_director_rejects_an_off_brand_accent(online, client, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "style": "premium-modern",
                "overlay": "dark_flat",
                "overlay_strength": 0.6,
                "crop": "focal",
                "text_align": "left",
                "logo_position": "top-left",
                "accent_color": "#00FF00",
            },
            "submit_design_specification",
        ),
    )
    spec = direct_design(
        client,
        _planned(),
        FlyerCopy(headline="Test Headline", cta="Call Now"),
        None,
        None,
        None,
        "",
        CanvasSpec(),
        "flyer_1",
        claude=online,
    )
    assert spec.palette["accent"] == client.brand.accent


def test_director_falls_back_to_layout_defaults(online, client, monkeypatch):
    monkeypatch.setattr(online, "_call", MagicMock(side_effect=AIError("down")))
    spec = direct_design(
        client,
        _planned(),
        FlyerCopy(headline="Test Headline", cta="Call Now"),
        None,
        None,
        None,
        "",
        CanvasSpec(),
        "flyer_1",
        claude=online,
    )
    assert spec.layout.name == "hero-full"
    assert spec.image.overlay != "none"


def test_director_picks_a_valid_type_pairing(online, client, monkeypatch):
    from app.rendering.typography import list_pairings

    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "style": "premium-modern",
                "overlay": "dark_flat",
                "overlay_strength": 0.6,
                "crop": "focal",
                "text_align": "left",
                "logo_position": "top-left",
                "type_pairing": "not-a-real-pairing",
            },
            "submit_design_specification",
        ),
    )
    spec = direct_design(
        client,
        _planned(),
        FlyerCopy(headline="Test Headline", cta="Call Now"),
        None,
        None,
        None,
        "",
        CanvasSpec(),
        "flyer_1",
        claude=online,
    )
    assert spec.layout.type_pairing in list_pairings()


# ------------------------------------------------------- reference analysis


def test_reference_analysis_returns_structured_metadata(online, repo, monkeypatch):
    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "category": "roofing",
                "style": "premium-modern",
                "layout": "hero-background",
                "text_density": "low",
                "visual_weight": "image-heavy",
                "cta_position": "bottom-left",
                "image_treatment": "dark-gradient",
                "description": "A restrained hero layout.",
                "suggested_layouts": ["hero-full"],
            },
            "record_reference_metadata",
        ),
    )
    path = repo / "references" / "inbox" / "example.jpg"
    Image.new("RGB", (1080, 1350), (90, 100, 110)).save(path)
    result = analyze_reference(path, ["roof-replacement"], claude=online)
    assert result["category"] == "roofing"
    assert result["suggested_layouts"] == ["hero-full"]


def test_reference_analysis_requires_claude(repo):
    path = repo / "references" / "inbox" / "example.jpg"
    Image.new("RGB", (400, 500)).save(path)
    with pytest.raises(AIError, match="requires Claude"):
        analyze_reference(path, [])


# --------------------------------------------------------------- vision QA


def test_vision_qa_is_skipped_when_claude_is_off(repo, client, tmp_path):
    from app.models import FlyerSpecification, ImageSpec, LayoutSpec

    path = tmp_path / "f.png"
    Image.new("RGB", (1080, 1350), (40, 50, 60)).save(path)
    spec = FlyerSpecification(
        id="x",
        client_id="testco",
        campaign_id="roof-replacement",
        service="roofing",
        layout=LayoutSpec(name="hero-full"),
        image=ImageSpec(),
        text=FlyerCopy(headline="Test", cta="Call"),
    )
    assert vision_qa(path, spec, client) is None


def test_vision_qa_maps_issues_to_severity(online, client, tmp_path, monkeypatch):
    from app.models import FlyerSpecification, ImageSpec, LayoutSpec, Severity

    monkeypatch.setattr(
        online,
        "_call",
        lambda **kw: _tool_response(
            {
                "passed": False,
                "score": 55,
                "issues": [
                    {
                        "check": "headline_readability",
                        "severity": "error",
                        "message": "Headline is too small",
                    },
                    {"check": "margins", "severity": "warning", "message": "Tight margin"},
                ],
            },
            "submit_qa_review",
        ),
    )
    path = tmp_path / "f.png"
    Image.new("RGB", (1080, 1350), (40, 50, 60)).save(path)
    spec = FlyerSpecification(
        id="x",
        client_id="testco",
        campaign_id="roof-replacement",
        service="roofing",
        layout=LayoutSpec(name="hero-full"),
        image=ImageSpec(),
        text=FlyerCopy(headline="Test", cta="Call"),
    )
    result = vision_qa(path, spec, client, claude=online)
    assert not result.passed
    assert result.issues[0].severity is Severity.ERROR
    assert result.warnings[0].check == "margins"


def test_vision_qa_failure_does_not_break_the_run(online, client, tmp_path, monkeypatch):
    from app.models import FlyerSpecification, ImageSpec, LayoutSpec

    monkeypatch.setattr(online, "_call", MagicMock(side_effect=AIError("down")))
    path = tmp_path / "f.png"
    Image.new("RGB", (1080, 1350), (40, 50, 60)).save(path)
    spec = FlyerSpecification(
        id="x",
        client_id="testco",
        campaign_id="roof-replacement",
        service="roofing",
        layout=LayoutSpec(name="hero-full"),
        image=ImageSpec(),
        text=FlyerCopy(headline="Test", cta="Call"),
    )
    assert vision_qa(path, spec, client, claude=online) is None
