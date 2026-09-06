"""Connector selection, priority and graceful degradation.

Mirrors TEST A..H from the integration brief. Every external service is
mocked; no unit test may reach a live API.
"""

from __future__ import annotations

import pytest

from app.connectors import (
    ConnectorOverrides,
    ConnectorResult,
    ConnectorRole,
    ConnectorStatus,
    SourceRef,
    decide,
    parse_overrides,
    status_report,
)
from app.connectors.adapters import ADAPTERS, UnsplashConnector
from app.connectors.base import BaseConnector


@pytest.fixture(autouse=True)
def _fresh_registry(repo):
    from app.connectors import clear_cache

    clear_cache()
    yield
    clear_cache()


class _Reachable(BaseConnector):
    """A connector that is available and returns one item."""

    def __init__(self, name, role, items=None):
        super().__init__({"enabled": True})
        self.name = name
        self.role = role
        self._items = items or [{"ok": True}]

    def _probe(self):
        return ConnectorStatus.AVAILABLE

    def _search(self, query, limit, **kwargs):
        return ConnectorResult(status=ConnectorStatus.AVAILABLE, items=self._items[:limit])


@pytest.fixture()
def all_reachable(monkeypatch):
    """Pretend every connector is authorised and healthy."""
    import app.connectors.registry as registry_module

    fake = {
        "unsplash": _Reachable("unsplash", ConnectorRole.ASSET),
        "mobbin": _Reachable("mobbin", ConnectorRole.REFERENCE),
        "figma": _Reachable("figma", ConnectorRole.TEMPLATE),
        "canva": _Reachable("canva", ConnectorRole.PRODUCTION),
    }
    monkeypatch.setattr(registry_module, "all_connectors", lambda: fake)
    monkeypatch.setattr("app.connectors.policy.all_connectors", lambda: fake)
    monkeypatch.setattr("app.connectors.policy.available_names", lambda: list(fake))
    return fake


# ------------------------------------------------------------------ registry


def test_all_four_connectors_are_registered(repo):
    assert set(ADAPTERS) == {"unsplash", "mobbin", "figma", "canva"}


def test_status_report_covers_every_connector(repo):
    report = status_report()
    assert set(report) == {"unsplash", "mobbin", "figma", "canva"}
    for info in report.values():
        assert info["status"] in {
            "available",
            "config_required",
            "not_installed",
            "disabled",
            "failed",
        }
        assert info["fallback"], "every connector must document its fallback"


def test_connectors_are_unavailable_without_credentials(repo):
    """Honest default: nothing external is reachable out of the box."""
    for info in status_report().values():
        assert info["status"] != "available"


def test_a_connector_never_raises(repo):
    result = UnsplashConnector({"enabled": True}).search("roofing")
    assert isinstance(result, ConnectorResult)
    assert not result.ok
    assert "internal" in result.message.lower()


def test_a_failing_connector_degrades_instead_of_raising(repo):
    class Exploding(BaseConnector):
        name = "boom"
        role = ConnectorRole.ASSET

        def _probe(self):
            return ConnectorStatus.AVAILABLE

        def _search(self, query, limit, **kwargs):
            raise RuntimeError("upstream on fire")

    result = Exploding({"enabled": True}).search("roofing")
    assert result.status is ConnectorStatus.FAILED
    assert "Falling back to internal sources" in result.message


def test_a_disabled_connector_reports_disabled(repo):
    assert UnsplashConnector({"enabled": False}).probe() is ConnectorStatus.DISABLED


# ------------------------------------------------------- the eight scenarios


def test_A_internal_references_are_sufficient(repo, all_reachable):
    decision = decide(
        has_suitable_asset=True, internal_reference_count=8, best_reference_score=0.85
    )
    assert decision.tools_used == []
    assert "unsplash" in decision.skipped
    assert "mobbin" in decision.skipped


def test_B_no_background_permits_unsplash(repo, all_reachable):
    decision = decide(
        has_suitable_asset=False, internal_reference_count=8, best_reference_score=0.85
    )
    assert decision.use_unsplash is True
    assert decision.need_stock_photo is True


def test_C_a_thin_reference_library_permits_pattern_research(repo, all_reachable):
    decision = decide(has_suitable_asset=True, internal_reference_count=0, best_reference_score=0.0)
    assert decision.use_mobbin is True
    assert decision.need_external_reference is True


def test_C2_a_weak_match_also_permits_it(repo, all_reachable):
    decision = decide(
        has_suitable_asset=True, internal_reference_count=20, best_reference_score=0.10
    )
    assert decision.use_mobbin is True


def test_D_an_editable_deliverable_selects_canva(repo, all_reachable):
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        editable_deliverable_requested=True,
    )
    assert decision.use_canva is True


def test_D2_figma_covers_editable_when_canva_is_down(repo, all_reachable, monkeypatch):
    without_canva = {k: v for k, v in all_reachable.items() if k != "canva"}
    monkeypatch.setattr("app.connectors.policy.available_names", lambda: list(without_canva))
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        editable_deliverable_requested=True,
    )
    assert decision.use_figma is True and decision.use_canva is False


def test_E_unsplash_unavailable_falls_back_internally(repo):
    decision = decide(
        has_suitable_asset=False, internal_reference_count=8, best_reference_score=0.85
    )
    assert decision.use_unsplash is False
    assert "procedural brand background" in decision.explain()


def test_F_canva_unavailable_falls_back_to_the_renderer(repo):
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        editable_deliverable_requested=True,
    )
    assert decision.use_canva is False
    assert "rendered PNG" in decision.explain()


def test_G_an_explicit_request_is_honoured(repo, all_reachable):
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        overrides=parse_overrides("use canva for this one"),
    )
    assert decision.use_canva is True
    assert "force:canva" in decision.overrides_applied


def test_G2_an_explicit_request_for_an_unavailable_tool_degrades(repo):
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        overrides=parse_overrides("use canva"),
    )
    assert decision.use_canva is False
    assert "not available" in decision.explain()


def test_H_internal_only_blocks_everything(repo, all_reachable):
    decision = decide(
        has_suitable_asset=False,
        internal_reference_count=0,
        best_reference_score=0.0,
        editable_deliverable_requested=True,
        overrides=parse_overrides("use internal assets only"),
    )
    assert decision.tools_used == []
    assert set(decision.skipped) == set(all_reachable)


def test_no_stock_photography_blocks_only_unsplash(repo, all_reachable):
    decision = decide(
        has_suitable_asset=False,
        internal_reference_count=0,
        best_reference_score=0.0,
        overrides=parse_overrides("no stock photography"),
    )
    assert decision.use_unsplash is False
    assert decision.use_mobbin is True


def test_template_work_selects_figma(repo, all_reachable):
    decision = decide(
        has_suitable_asset=True,
        internal_reference_count=8,
        best_reference_score=0.85,
        building_template_system=True,
    )
    assert decision.use_figma is True


# ------------------------------------------------------------------ overrides


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("internal references only", {"internal_only": True}),
        ("do not use external sources", {"internal_only": True}),
        ("no stock photography", {"no_stock_photography": True}),
        ("use canva", {"force": ["canva"]}),
        ("use unsplash for the background", {"force": ["unsplash"]}),
        ("use mobbin for layout inspiration", {"force": ["mobbin"]}),
    ],
)
def test_override_phrases_are_understood(repo, phrase, expected):
    overrides = parse_overrides(phrase)
    for key, value in expected.items():
        assert getattr(overrides, key) == value, phrase


def test_no_phrase_means_no_overrides(repo):
    assert parse_overrides(None).is_empty
    assert parse_overrides("").is_empty


def test_forbid_beats_force(repo):
    overrides = ConnectorOverrides(force=["unsplash"], forbid=["unsplash"])
    decision = decide(
        has_suitable_asset=False,
        internal_reference_count=0,
        best_reference_score=0.0,
        overrides=overrides,
    )
    assert decision.use_unsplash is False


# ---------------------------------------------------------------- provenance


def test_source_ref_records_full_provenance():
    ref = SourceRef(
        source="unsplash",
        source_id="abc123",
        source_url="https://unsplash.com/photos/abc123",
        author="A Photographer",
        licence="Unsplash License",
        usage_context="background photography",
    )
    assert not ref.is_internal
    assert ref.retrieved_at


def test_internal_sources_are_recognised():
    assert SourceRef(source="internal").is_internal
    assert SourceRef(source="client").is_internal


def test_source_scores_put_internal_work_first(repo):
    from app.config import load_json_config

    scores = load_json_config("connectors.json")["reference_source_scores"]
    assert scores["internal_approved_client_design"] >= scores["internal_approved"]
    assert scores["internal_approved"] > scores["figma"] > scores["canva"] > scores["mobbin"]
    assert scores["mobbin"] > scores["unsplash"]
    assert scores["rejected"] == 0.0

    assets = load_json_config("connectors.json")["asset_source_scores"]
    assert assets["client"] > assets["internal_approved"] > assets["unsplash"]


# ------------------------------------------------------------------ pipeline


def test_a_generated_flyer_records_its_tool_decision(repo):
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False)
    decision = run.results[0].spec.tool_decision
    assert "reasons" in decision and decision["reasons"]
    assert "skipped" in decision


def test_history_records_which_tools_were_used(repo):
    from app.pipeline import history
    from app.pipeline.generate import generate_flyers

    generate_flyers(client_id="testco", count=1, upload=False)
    entry = history.for_client("testco")[0]
    assert "tools_used" in entry and "renderer" in entry
    assert entry["renderer"] == "internal"


def test_a_run_with_no_connectors_still_completes(repo):
    """CONNECTOR FAILURE: none available is the default, and it must work."""
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=2, upload=False)
    assert run.succeeded == 2
    assert run.tools_used == ["offline-fallback"]


def test_internal_only_override_reaches_the_pipeline(repo):
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, tools="internal only")
    decision = run.results[0].spec.tool_decision
    assert decision["overrides_applied"] == ["internal-only"]
