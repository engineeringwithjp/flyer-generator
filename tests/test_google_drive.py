"""Tests for Google Drive uploader and offline simulation."""

from src.services.google_drive import GoogleDriveUploader


def test_google_drive_offline_simulation(tmp_path):
    uploader = GoogleDriveUploader(
        service_account_path=None,
        service_account_json=None
    )
    dummy_file = tmp_path / "flyer.png"
    dummy_file.write_text("fake png content")

    res = uploader.upload_flyer(str(dummy_file), "All Elite Construction")
    assert res["status"] == "offline_simulated"
    assert "gdrive_mock" in res["file_id"]
    assert res["folder_id"] == "12Ho15EiJumnZkSAPm0I1Zd9Vwe6CuLiT"
