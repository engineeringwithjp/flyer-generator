"""Asset cataloguing, selection scoring, and the reference library."""

from __future__ import annotations

import pytest
from PIL import Image

from app import references as reference_lib
from app.assets.catalog import AssetCatalog, refresh_asset_index
from app.assets.image_utils import analyse_image, crop_to_aspect, ensure_readable, load_rgb
from app.assets.selector import score_asset, select_asset, select_pair
from app.errors import AssetError
from app.models import FocalPoint, ReferenceImage, ReferenceStatus

# ------------------------------------------------------------------- catalog


def test_catalog_finds_shared_and_client_assets(repo):
    catalog = AssetCatalog.load(refresh=True)
    ids = {a.id for a in catalog.index.assets}
    assert any("roofing:roof-one" in i for i in ids)
    assert any("testco" in i for i in ids)


def test_logos_are_never_catalogued_as_photography(repo):
    catalog = AssetCatalog.load(refresh=True)
    assert not any("logo" in a.path for a in catalog.index.assets)


def test_service_is_derived_from_the_folder(repo):
    catalog = AssetCatalog.load(refresh=True)
    roof = next(a for a in catalog.index.assets if "roof-one" in a.id)
    assert roof.service == "roofing"


def test_client_assets_are_marked_as_owned(repo):
    catalog = AssetCatalog.load(refresh=True)
    owned = [a for a in catalog.index.assets if a.is_client_owned]
    assert owned and all(a.client_id == "testco" for a in owned)


def test_client_assets_are_returned_first(repo):
    catalog = AssetCatalog.load(refresh=True)
    ordered = catalog.for_client("testco")
    assert ordered[0].is_client_owned


def test_usage_counters_survive_a_reindex(repo):
    catalog = AssetCatalog.load(refresh=True)
    asset_id = catalog.index.assets[0].id
    catalog.mark_used(asset_id, "2026-09-05T10:00:00")
    fresh = refresh_asset_index()
    assert fresh.by_id(asset_id).times_used == 1


def test_hidden_directories_inside_the_library_are_skipped(repo):
    hidden = repo / "assets" / ".cache"
    hidden.mkdir()
    Image.new("RGB", (100, 100)).save(hidden / "junk.jpg")
    catalog = AssetCatalog.load(refresh=True)
    assert not any(".cache" in a.path for a in catalog.index.assets)


def test_a_dotted_parent_directory_does_not_hide_the_whole_library(repo):
    """Regression: the repo itself can live under a dotted path (a git worktree)."""
    catalog = AssetCatalog.load(refresh=True)
    assert len(catalog.index.assets) >= 4


# --------------------------------------------------------------- image utils


def test_corrupt_image_raises_asset_error(repo):
    bad = repo / "assets" / "roofing" / "corrupt.jpg"
    bad.write_bytes(b"this is definitely not a jpeg")
    with pytest.raises(AssetError):
        ensure_readable(bad)


def test_empty_file_raises_asset_error(repo):
    empty = repo / "assets" / "roofing" / "empty.jpg"
    empty.touch()
    with pytest.raises(AssetError, match="empty"):
        ensure_readable(empty)


def test_unsupported_type_raises_asset_error(repo):
    bad = repo / "assets" / "roofing" / "notes.txt"
    bad.write_text("hello")
    with pytest.raises(AssetError, match="Unsupported"):
        ensure_readable(bad)


def test_corrupt_asset_is_skipped_not_fatal(repo):
    (repo / "assets" / "roofing" / "corrupt.jpg").write_bytes(b"nope")
    catalog = AssetCatalog.load(refresh=True)
    assert catalog.index.assets  # the rest of the library still catalogues


def test_analysis_reports_plausible_values(repo):
    analysis = analyse_image(repo / "assets" / "roofing" / "roof-one.jpg")
    assert 0.0 <= analysis["mean_luminance"] <= 1.0
    assert 0.0 <= analysis["contrast"] <= 1.0
    assert analysis["width"] == 1600 and analysis["height"] == 1200
    assert len(analysis["sha256"]) == 64


@pytest.mark.parametrize("size", [(1080, 1350), (1080, 1080), (1200, 628), (1080, 1920)])
def test_crop_hits_the_exact_target_size(repo, size):
    source = load_rgb(repo / "assets" / "roofing" / "roof-one.jpg")
    assert crop_to_aspect(source, size[0], size[1], "focal", FocalPoint()).size == size


def test_crop_rejects_a_zero_size_target(repo):
    source = load_rgb(repo / "assets" / "roofing" / "roof-one.jpg")
    with pytest.raises(AssetError):
        crop_to_aspect(source, 0, 100)


# ------------------------------------------------------------------ selection


def test_selection_prefers_a_matching_service(repo):
    catalog = AssetCatalog.load(refresh=True)
    chosen = select_asset(catalog, "testco", "roofing", "hero-full")
    assert chosen is not None and chosen.service == "roofing"


def test_selection_is_deterministic(repo):
    catalog = AssetCatalog.load(refresh=True)
    first = select_asset(catalog, "testco", "roofing", "hero-full")
    second = select_asset(catalog, "testco", "roofing", "hero-full")
    assert first.id == second.id


def test_recently_used_assets_are_penalised(repo):
    catalog = AssetCatalog.load(refresh=True)
    first = select_asset(catalog, "testco", "roofing", "hero-full")
    second = select_asset(catalog, "testco", "roofing", "hero-full", recent_asset_ids=[first.id])
    assert second.id != first.id


def test_exclusion_is_honoured(repo):
    catalog = AssetCatalog.load(refresh=True)
    first = select_asset(catalog, "testco", "roofing", "hero-full")
    second = select_asset(catalog, "testco", "roofing", "hero-full", exclude={first.id})
    assert second.id != first.id


def test_client_owned_assets_outscore_shared_ones(repo):
    catalog = AssetCatalog.load(refresh=True)
    owned = next(a for a in catalog.index.assets if a.is_client_owned)
    shared = next(
        a for a in catalog.index.assets if not a.is_client_owned and a.service == "roofing"
    )
    assert score_asset(owned, "roofing", "hero-full", []) > score_asset(
        shared, "roofing", "hero-full", []
    )


def test_pair_selection_returns_two_distinct_assets(repo):
    catalog = AssetCatalog.load(refresh=True)
    first, second = select_pair(catalog, "testco", "roofing", "before-after")
    assert first and second and first.id != second.id


def test_empty_library_returns_none_rather_than_raising(repo):
    from app.models import AssetIndex

    assert select_asset(AssetCatalog(AssetIndex()), "testco", "roofing", "hero-full") is None


# ------------------------------------------------------------------ references


def _reference(ref_id: str, **overrides) -> ReferenceImage:
    payload = {
        "id": ref_id,
        "filename": f"{ref_id}.jpg",
        "path": f"references/experimental/{ref_id}.jpg",
        "status": ReferenceStatus.EXPERIMENTAL,
        "category": "roofing",
        "style": "premium-modern",
        "suggested_layouts": ["hero-full"],
        "recommended_campaigns": ["roof-replacement"],
    }
    payload.update(overrides)
    return ReferenceImage.model_validate(payload)


def test_rejected_references_are_never_selected(repo, client):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001", status=ReferenceStatus.REJECTED))
    reference_lib.save_index(index)
    assert (
        reference_lib.select_reference("roofing", "roof-replacement", "hero-full", client) is None
    )


def test_approved_beats_experimental(repo, client):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001", status=ReferenceStatus.EXPERIMENTAL))
    index.upsert(_reference("ref_000002", status=ReferenceStatus.APPROVED))
    reference_lib.save_index(index)
    chosen = reference_lib.select_reference("roofing", "roof-replacement", "hero-full", client)
    assert chosen.id == "ref_000002"


def test_service_relevance_beats_a_generic_reference(repo, client):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001", category="general"))
    index.upsert(_reference("ref_000002", category="roofing"))
    reference_lib.save_index(index)
    chosen = reference_lib.select_reference("roofing", "roof-replacement", "hero-full", client)
    assert chosen.id == "ref_000002"


def test_empty_library_selects_nothing_without_error(repo, client):
    assert (
        reference_lib.select_reference("roofing", "roof-replacement", "hero-full", client) is None
    )


def test_approval_feedback_moves_the_score(repo, client):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001"))
    reference_lib.save_index(index)
    before = reference_lib.load_index().by_id("ref_000001").performance
    reference_lib.record_outcome(["ref_000001"], approved=True)
    after = reference_lib.load_index().by_id("ref_000001").performance
    assert after > before


def test_rejection_feedback_lowers_the_score(repo, client):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001"))
    reference_lib.save_index(index)
    reference_lib.record_outcome(["ref_000001"], approved=False)
    assert reference_lib.load_index().by_id("ref_000001").performance < 0.5


def test_promote_moves_the_file_and_the_sidecar(repo):
    source = repo / "references" / "experimental" / "ref_000001.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 1000), (120, 130, 140)).save(source)

    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001"))
    reference_lib.save_index(index)

    promoted = reference_lib.promote("ref_000001", ReferenceStatus.APPROVED)
    assert promoted.status is ReferenceStatus.APPROVED
    assert (repo / promoted.path).exists()
    assert (repo / promoted.path).with_suffix(".json").exists()
    assert not source.exists()


def test_reference_ids_increment(repo):
    index = reference_lib.load_index()
    assert index.next_id() == "ref_000001"
    index.upsert(_reference("ref_000001"))
    assert index.next_id() == "ref_000002"


def test_index_survives_a_round_trip(repo):
    index = reference_lib.load_index()
    index.upsert(_reference("ref_000001", description="A design"))
    reference_lib.save_index(index)
    assert reference_lib.load_index().by_id("ref_000001").description == "A design"


def test_design_references_and_photography_are_separate_libraries(repo):
    """SUCCESS CRITERION 6: inspiration is never used as flyer content."""
    source = repo / "references" / "approved" / "roofing" / "ref_000001.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 1000), (100, 110, 120)).save(source)
    catalog = AssetCatalog.load(refresh=True)
    assert not any("references" in a.path for a in catalog.index.assets)
