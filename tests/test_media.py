"""Media ingestion: discovery, frame scoring, deduplication, provenance.

No test decodes real video. ffmpeg-dependent paths are mocked, so the suite
runs anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.media.frames import (
    centre_crop_to_flyer,
    dhash,
    hamming,
    sample_times,
    score_frame,
)
from app.media.probe import MediaItem, scan_directory

# ------------------------------------------------------------------ discovery


def _video(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 2048)


def test_scan_finds_videos_and_photos(repo, tmp_path):
    root = tmp_path / "card"
    _video(root / "DJI_0001.MP4")
    _video(root / "DJI_0002.mov")
    Image.new("RGB", (400, 300)).save(root / "DJI_0003.JPG")

    items = scan_directory(root)
    kinds = sorted(i.kind for i in items)
    assert kinds == ["photo", "video", "video"]


def test_scan_skips_appledouble_stubs(repo, tmp_path):
    """A Samsung/DJI card is full of ._NAME.MP4 metadata stubs."""
    root = tmp_path / "card"
    _video(root / "DJI_0001.MP4")
    _video(root / "._DJI_0001.MP4")

    items = scan_directory(root)
    assert len(items) == 1
    assert not items[0].path.name.startswith("._")


def test_scan_ignores_unrelated_files(repo, tmp_path):
    root = tmp_path / "card"
    root.mkdir()
    (root / "notes.txt").write_text("hello")
    (root / "DJI_0001.SRT").write_text("subtitles")
    assert scan_directory(root) == []


def test_scan_raises_on_a_missing_path(repo, tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_directory(tmp_path / "no-such-card")


def test_media_item_reports_4k(repo):
    assert MediaItem(path=Path("a.mp4"), kind="video", width=3840, height=2160).is_4k
    assert not MediaItem(path=Path("a.mp4"), kind="video", width=1280, height=720).is_4k


# --------------------------------------------------------------------- timing


def test_sample_times_avoids_the_clip_edges():
    times = sample_times(100.0, 5)
    assert len(times) == 5
    assert times[0] > 0, "takeoff should be skipped"
    assert times[-1] < 100.0, "landing should be skipped"
    assert times == sorted(times)


def test_sample_times_handles_a_very_short_clip():
    assert len(sample_times(1.2, 4)) == 4


def test_sample_times_handles_a_single_sample():
    assert len(sample_times(30.0, 1)) == 1


def test_sample_times_handles_zero_duration():
    assert sample_times(0.0, 5) == [0.0]


# --------------------------------------------------------------------- crop


def test_centre_crop_produces_the_flyer_aspect():
    cropped = centre_crop_to_flyer(Image.new("RGB", (3840, 2160)))
    ratio = cropped.width / cropped.height
    assert ratio == pytest.approx(1080 / 1350, rel=0.01)


def test_centre_crop_handles_portrait_input():
    cropped = centre_crop_to_flyer(Image.new("RGB", (1080, 3000)))
    assert cropped.width / cropped.height == pytest.approx(1080 / 1350, rel=0.01)


# -------------------------------------------------------------------- scoring


def _noisy(size=(1600, 900), step=7):
    """High-detail image: sharp, high contrast, no calm band."""
    image = Image.new("RGB", size, (40, 44, 50))
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], step):
        draw.line([(x, 0), (x, size[1])], fill=(220, 225, 230), width=2)
    for y in range(0, size[1], step):
        draw.line([(0, y), (size[0], y)], fill=(90, 95, 100), width=1)
    return image


def test_a_flat_frame_scores_poorly():
    total, scores = score_frame(Image.new("RGB", (1600, 900), (128, 128, 128)))
    assert total < 0.45
    assert scores["sharpness"] < 0.1
    assert scores["contrast"] < 0.1


def test_a_detailed_frame_beats_a_flat_one():
    flat, _ = score_frame(Image.new("RGB", (1600, 900), (128, 128, 128)))
    busy, _ = score_frame(_noisy())
    assert busy > flat


def test_a_black_frame_scores_badly_on_exposure():
    _, scores = score_frame(Image.new("RGB", (1600, 900), (2, 2, 2)))
    assert scores["exposure"] < 0.1


def test_a_blown_out_frame_scores_badly_on_exposure():
    _, scores = score_frame(Image.new("RGB", (1600, 900), (252, 252, 252)))
    assert scores["exposure"] < 0.1


def test_scores_stay_within_bounds():
    for image in (Image.new("RGB", (1600, 900), (128, 128, 128)), _noisy()):
        total, scores = score_frame(image)
        assert 0.0 <= total <= 1.0
        for value in scores.values():
            assert 0.0 <= value <= 1.0


def test_scoring_is_deterministic():
    image = _noisy()
    assert score_frame(image)[0] == score_frame(image)[0]


def test_a_calm_band_raises_the_negative_space_score():
    """Sky at the top is exactly what a headline needs."""
    busy = _noisy()
    with_sky = busy.copy()
    ImageDraw.Draw(with_sky).rectangle(
        (0, 0, with_sky.width, int(with_sky.height * 0.34)), fill=(150, 175, 205)
    )
    assert score_frame(with_sky)[1]["negative_space"] > score_frame(busy)[1]["negative_space"]


# ---------------------------------------------------------------- duplicates


def test_identical_frames_hash_identically():
    image = _noisy()
    assert dhash(image) == dhash(image.copy())


def test_hamming_distance_of_identical_hashes_is_zero():
    assert hamming(dhash(_noisy()), dhash(_noisy())) == 0


def test_a_very_different_frame_hashes_differently():
    a = dhash(Image.new("RGB", (800, 600), (10, 10, 10)))
    b = dhash(_noisy((800, 600)))
    assert hamming(a, b) > 5


def test_near_identical_frames_are_close():
    """Hovering drone footage produces near-duplicate samples."""
    base = _noisy()
    nudged = base.crop((4, 0, base.width, base.height)).resize(base.size)
    assert hamming(dhash(base), dhash(nudged)) < 20


# --------------------------------------------------------------- provenance


def test_extracted_frames_are_real_but_unapproved(repo):
    """The core boundary: real media still needs a human before production."""
    from app.assets.metadata import derive_provenance
    from app.models import ApprovalStatus, SourceType

    frame = repo / "clients" / "testco" / "assets" / "raw" / "frames" / "dji_0001_frame_12s.jpg"
    frame.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (3840, 2160), (100, 110, 120)).save(frame)

    provenance = derive_provenance(frame)
    assert provenance["source_type"] == SourceType.CLIENT_VIDEO_FRAME
    assert provenance["approval_status"] == ApprovalStatus.UNAPPROVED


def test_a_sidecar_overrides_derived_metadata(repo):
    from app.assets.catalog import AssetCatalog

    frame = repo / "clients" / "testco" / "assets" / "raw" / "frames" / "dji_0002_frame_8s.jpg"
    frame.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 1200), (100, 110, 120)).save(frame)
    frame.with_suffix(".json").write_text(
        json.dumps({"quality_score": 0.77, "service": "roofing"}), encoding="utf-8"
    )

    catalog = AssetCatalog.load(refresh=True)
    asset = next(a for a in catalog.index.assets if "dji_0002" in a.id)
    assert asset.quality_score == 0.77
    assert asset.service == "roofing"


def test_ingest_reports_missing_ffmpeg(repo, tmp_path, monkeypatch):
    from app.media import ingest as ingest_module

    monkeypatch.setattr(ingest_module, "ffmpeg_available", lambda: False)
    report = ingest_module.ingest_media(tmp_path, "testco")
    assert report.frames_kept == 0
    assert any("ffmpeg" in e for e in report.errors)
