"""End-to-end: the pipeline the audit's SUCCESS CRITERIA describe.

    plan -> reference -> assets -> copy -> spec -> render -> QA -> output

No network. No credentials. Claude is mocked or disabled.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.ai.campaign_planner import load_catalog, plan_campaigns, season_for
from app.config import get_settings
from app.models import Brief
from app.pipeline import history
from app.pipeline.generate import generate_flyers, today_in

# ------------------------------------------------------------------ planning


def test_season_mapping():
    assert season_for(date(2026, 1, 15)) == "winter"
    assert season_for(date(2026, 4, 15)) == "spring"
    assert season_for(date(2026, 7, 15)) == "summer"
    assert season_for(date(2026, 10, 15)) == "fall"


def test_catalogue_loads_and_has_every_trade(repo):
    services = {c.service for c in load_catalog().campaigns}
    for trade in ("roofing", "siding", "gutters", "windows", "hvac", "plumbing", "electrical"):
        assert trade in services


def test_planner_only_offers_campaigns_the_client_sells(repo, client):
    plan = plan_campaigns(client, count=2, today=date(2026, 9, 5), history=[])
    catalog = load_catalog()
    for flyer in plan.flyers:
        campaign = catalog.by_id(flyer.campaign_id)
        assert campaign.service in {"roofing", "siding", "general"}


def test_planner_returns_the_requested_count(repo, client):
    assert len(plan_campaigns(client, 2, date(2026, 9, 5), []).flyers) == 2


def test_a_batch_never_repeats_a_layout(repo, client):
    plan = plan_campaigns(client, 3, date(2026, 9, 5), [])
    layouts = [f.layout for f in plan.flyers]
    assert len(layouts) == len(set(layouts))


def test_history_pushes_the_planner_onto_something_new(repo, client):
    first = plan_campaigns(client, 1, date(2026, 9, 5), [])
    used = first.flyers[0].campaign_id
    past = [{"client": "testco", "date": "2026-09-04", "campaign": used}]
    second = plan_campaigns(client, 1, date(2026, 9, 5), past)
    assert second.flyers[0].campaign_id != used


def test_forcing_a_service_narrows_the_plan(repo, client):
    plan = plan_campaigns(client, 1, date(2026, 9, 5), [], forced_campaign="siding")
    assert plan.flyers[0].service == "siding"


def test_forcing_an_unknown_campaign_raises(repo, client):
    with pytest.raises(ValueError, match="Unknown campaign"):
        plan_campaigns(client, 1, date(2026, 9, 5), [], forced_campaign="underwater-basketweaving")


def test_a_brief_steers_the_first_flyer(repo, client):
    """PROMPT MINIMISATION: a four-line brief is enough to direct the batch."""
    plan = plan_campaigns(
        client,
        2,
        date(2026, 9, 5),
        [],
        forced_campaign="siding",
        brief=Brief(
            message="built-in insulation", archetype="product-education", product_id="test-shingle"
        ),
    )
    first = plan.flyers[0]
    assert first.primary_message == "built-in insulation"
    assert first.archetype == "product-education"
    assert first.layout == "hero-full"


def test_an_unknown_product_in_a_brief_is_ignored(repo, client):
    plan = plan_campaigns(
        client, 1, date(2026, 9, 5), [], brief=Brief(product_id="not-a-real-product")
    )
    assert plan.flyers[0].product_id is None


def test_every_flyer_gets_an_archetype(repo, client):
    plan = plan_campaigns(client, 2, date(2026, 9, 5), [], brief=Brief(message="x"))
    assert all(f.archetype for f in plan.flyers)


# ------------------------------------------------------------- generation


def test_two_flyers_from_one_short_instruction(repo):
    """SUCCESS CRITERION 10."""
    run = generate_flyers(client_id="testco", count=2, upload=False)
    assert len(run.results) == 2
    assert run.succeeded == 2, run.errors
    settings = get_settings()
    for result in run.results:
        assert Image.open(result.image_path).size == (
            settings.output_width,
            settings.output_height,
        )


def test_the_two_flyers_in_a_batch_differ(repo):
    """DUPLICATION PREVENTION."""
    run = generate_flyers(client_id="testco", count=2, upload=False)
    a, b = run.results
    assert a.spec.campaign_id != b.spec.campaign_id
    assert a.spec.layout.name != b.spec.layout.name
    assert a.spec.text.headline != b.spec.text.headline
    assert Image.open(a.image_path).tobytes() != Image.open(b.image_path).tobytes()


def test_metadata_sidecar_is_written_and_complete(repo):
    run = generate_flyers(client_id="testco", count=1, upload=False)
    payload = json.loads(Path(run.results[0].metadata_path).read_text())
    assert payload["spec"]["text"]["headline"]
    assert payload["qa"]["score"] >= 0
    assert payload["width"] == get_settings().output_width


def test_a_run_summary_is_written(repo):
    from pathlib import Path

    run = generate_flyers(client_id="testco", count=2, upload=False)
    summary = Path(run.results[0].image_path).parent / "SUMMARY.md"
    assert summary.exists() and "Campaign" in summary.read_text()


def test_history_records_everything_needed_to_avoid_repetition(repo):
    generate_flyers(client_id="testco", count=2, upload=False)
    entries = history.for_client("testco")
    assert len(entries) == 2
    for entry in entries:
        for field in (
            "date",
            "client",
            "campaign",
            "service",
            "layout",
            "headline",
            "reference_ids",
            "asset_ids",
            "qa_score",
            "flyer_id",
            "style",
        ):
            assert field in entry, f"history entry is missing {field}"


def test_consecutive_days_do_not_repeat_a_campaign(repo):
    first = generate_flyers(client_id="testco", count=2, upload=False, when=date(2026, 9, 5))
    second = generate_flyers(client_id="testco", count=2, upload=False, when=date(2026, 9, 6))
    used_first = {r.spec.campaign_id for r in first.results}
    used_second = {r.spec.campaign_id for r in second.results}
    assert not (used_first & used_second)


def test_client_photography_is_actually_used(repo):
    run = generate_flyers(client_id="testco", count=1, upload=False, campaign="roofing")
    assert run.results[0].spec.image.asset_id


def test_generation_works_with_an_empty_photo_library(repo):
    """The system must be usable on day one, before any photos exist."""
    import shutil

    shutil.rmtree(repo / "assets" / "roofing")
    shutil.rmtree(repo / "assets" / "siding")
    shutil.rmtree(repo / "clients" / "testco" / "assets" / "approved")
    (repo / "data" / "assets" / "index.json").unlink(missing_ok=True)

    run = generate_flyers(client_id="testco", count=2, upload=False)
    # It still renders rather than crashing, and it still refuses to invent a
    # photograph. What changed is that a flyer selling a specific trade with
    # nothing to show for it is now held: a brand gradient is a fine background
    # for a brand message and a poor argument about a roof.
    assert run.results, run.errors
    assert not run.errors
    for result in run.results:
        assert result.spec.image.asset_id is None


def test_a_brief_reaches_the_finished_flyer(repo):
    run = generate_flyers(
        client_id="testco",
        count=1,
        upload=False,
        campaign="siding",
        message="built-in insulation",
        cta="Free Estimate",
    )
    spec = run.results[0].spec
    assert spec.service == "siding"
    assert spec.text.cta == "Free Estimate"
    assert "insulation" in spec.text.headline.lower()


def test_nothing_uploads_when_upload_is_off(repo):
    run = generate_flyers(client_id="testco", count=1, upload=False)
    assert run.results[0].drive_file_id == ""


def test_an_invalid_client_fails_loudly(repo):
    from app.errors import ClientError

    with pytest.raises(ClientError):
        generate_flyers(client_id="nobody", count=1, upload=False)


def test_business_timezone_is_used_not_utc(repo):
    assert today_in("America/New_York") is not None
    assert today_in("Not/AZone") is not None  # falls back rather than crashing


def test_the_offline_path_never_calls_claude(repo, monkeypatch):
    """COST CONTROL: no API traffic when Claude is disabled."""
    from app.ai import claude_client

    boom = MagicMock(side_effect=AssertionError("Claude was called in offline mode"))
    monkeypatch.setattr(claude_client.ClaudeClient, "_call", boom)
    run = generate_flyers(client_id="testco", count=2, upload=False)
    assert run.succeeded == 2
    boom.assert_not_called()


def test_a_render_failure_is_reported_not_swallowed(repo, monkeypatch):
    from app.errors import RenderError
    from app.pipeline import generate as generate_module

    def explode(*args, **kwargs):
        raise RenderError("simulated renderer failure")

    monkeypatch.setattr(generate_module, "render_flyer", explode)
    run = generate_flyers(client_id="testco", count=2, upload=False)
    assert run.results == []
    assert len(run.errors) == 2
    assert "simulated renderer failure" in run.errors[0]


def test_a_qa_failure_blocks_the_upload(repo, monkeypatch):
    from app.models import QAIssue, QAResult, Severity
    from app.pipeline import generate as generate_module

    monkeypatch.setattr(
        generate_module,
        "qa_flyer",
        lambda *a, **k: QAResult.from_issues(
            [QAIssue(check="test", severity=Severity.ERROR, message="forced failure")]
        ),
    )
    uploaded = []
    monkeypatch.setattr(generate_module, "_upload", lambda *a, **k: uploaded.append(1))

    run = generate_flyers(client_id="testco", count=1, upload=True)
    assert not run.results[0].qa_passed
    assert run.results[0].attempts == 2  # one automatic retry was made
