"""Tests for 5-tier photo sourcing hierarchy."""

from src.core.asset_selector import AssetSelector


def test_select_background_prefers_client_photo():
    selector = AssetSelector()
    asset = selector.select_background("all-elite", "roofing")
    # All Elite has client photos in clients/all-elite/photos/
    assert asset.source == "client"
    assert "all-elite" in asset.file_path
