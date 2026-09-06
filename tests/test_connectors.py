"""Tests for connected design ecosystem and decision engine."""

from src.connectors.canva_connector import CanvaConnector
from src.connectors.decision_engine import ToolDecisionEngine
from src.connectors.figma_connector import FigmaConnector
from src.connectors.mobbin_connector import MobbinConnector
from src.connectors.unsplash_connector import UnsplashConnector


def test_decision_engine_internal_priority():
    engine = ToolDecisionEngine()
    decision = engine.evaluate(
        has_client_photos=True,
        has_internal_background=True,
        has_approved_references=True
    )
    assert decision.need_stock_photo is False
    assert decision.use_canva is False
    assert "satisfy design constraints" in decision.reason

def test_decision_engine_user_override():
    engine = ToolDecisionEngine()
    decision = engine.evaluate(
        has_client_photos=True,
        has_internal_background=True,
        has_approved_references=True,
        user_overrides={"force_canva": True}
    )
    assert decision.use_canva is True
    assert "Canva" in decision.reason

def test_connectors_graceful_offline_fallback():
    canva = CanvaConnector(api_key=None)
    figma = FigmaConnector(access_token=None)
    unsplash = UnsplashConnector(access_key=None)
    mobbin = MobbinConnector(api_key=None)

    assert canva.is_configured() is False
    assert canva.create_editable_design("test")["status"] == "fallback_internal"

    assert figma.is_configured() is False
    assert figma.get_master_components()["status"] == "fallback_internal"

    assert unsplash.is_configured() is False
    assert unsplash.search_photo("roof") is None

    assert mobbin.is_configured() is False
    assert len(mobbin.search_patterns()) > 0
