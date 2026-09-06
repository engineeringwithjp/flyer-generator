"""Writing flyers straight into a mounted Google Drive folder."""

from __future__ import annotations

from datetime import date

import pytest

from app.config import reset_settings_cache
from app.drive.local import describe, find_folder, is_available, resolve_output_dir


@pytest.fixture()
def mounted(repo, monkeypatch):
    """A stand-in for a Google Drive for Desktop mount."""
    mount = repo / "fake-drive" / "My Drive" / "NEDA" / "Client Flyers"
    mount.mkdir(parents=True)
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(mount))
    reset_settings_cache()
    return mount


def test_not_available_when_unset(repo):
    assert is_available() is False


def test_available_when_the_folder_exists(mounted):
    assert is_available() is True


def test_not_available_when_the_path_is_wrong(repo, monkeypatch):
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(repo / "no-such-folder"))
    reset_settings_cache()
    assert is_available() is False


def test_output_dir_mirrors_the_api_layout(mounted):
    target = resolve_output_dir("All Elite Roofing & Siding", date(2026, 9, 6))
    assert target is not None
    assert target.relative_to(mounted).parts == ("Flyers", "2026", "September", "09-06")
    assert target.is_dir()


def test_output_dir_matches_the_uploader_segments(mounted):
    """Both delivery paths must produce the same tree in Drive."""
    from app.drive.folders import flyer_folder_path

    api = flyer_folder_path("All Elite Roofing & Siding", date(2026, 9, 6))[1:]
    local = resolve_output_dir("All Elite Roofing & Siding", date(2026, 9, 6))
    assert list(local.relative_to(mounted).parts) == api


def test_output_dir_is_none_without_configuration(repo):
    assert resolve_output_dir("Any Co", date(2026, 9, 6)) is None


def test_a_vanished_mount_degrades_instead_of_crashing(repo, monkeypatch):
    """Drive for Desktop may be quit; the run must still produce flyers."""
    monkeypatch.setenv("DRIVE_LOCAL_PATH", str(repo / "gone"))
    reset_settings_cache()
    assert resolve_output_dir("Any Co", date(2026, 9, 6)) is None


def test_find_folder_returns_none_when_absent(repo):
    assert find_folder("Definitely Not A Real Folder Name Here") is None


def test_describe_reports_configuration(mounted):
    info = describe()
    assert info["configured_exists"] is True
    assert "Stream files" in info["streaming_hint"]


# --------------------------------------------------------------- pipeline


def test_flyers_are_written_into_drive_not_the_project(mounted, repo):
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, when=date(2026, 9, 6))
    assert run.results
    written = run.results[0].image_path
    assert str(mounted) in written, "flyer should be inside the Drive mount"
    assert not list((repo / "output").rglob("flyer-*.png")), "nothing in the project output/"


def test_the_project_is_used_when_drive_is_not_configured(repo):
    from app.pipeline.generate import generate_flyers

    run = generate_flyers(client_id="testco", count=1, upload=False, when=date(2026, 9, 6))
    assert "output" in run.results[0].image_path
