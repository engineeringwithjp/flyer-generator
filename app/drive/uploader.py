"""Upload flyers and their metadata to Google Drive.

Duplicate detection is by (folder, filename) plus an appProperties SHA-256, so
re-running a day's generation replaces the file rather than littering the folder
with ``flyer-01 (2).png``.
"""

from __future__ import annotations

import random
import time
from datetime import date
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..errors import DriveError
from ..logging_setup import get_logger
from ..models import Client, FlyerResult
from .auth import build_drive_service
from .folders import ensure_folder_path, flyer_folder_path

log = get_logger(__name__)

MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".json": "application/json",
}

MAX_ATTEMPTS = 4


class DriveUploader:
    def __init__(self, settings: Settings | None = None, service: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._service = service
        self._folder_cache: dict[tuple[str, str], str] = {}

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = build_drive_service(self.settings)
        return self._service

    @property
    def shared(self) -> bool:
        return self.settings.drive_is_shared_drive

    # ------------------------------------------------------------------ paths

    def resolve_root(self, client: Client) -> str:
        root = client.drive.root_folder_id or self.settings.drive_root_folder_id
        if not root:
            raise DriveError(
                f"No Drive folder for client {client.id!r}. Set drive.root_folder_id in "
                "client.json or GOOGLE_DRIVE_ROOT_FOLDER_ID in the environment."
            )
        return root

    def target_folder(self, client: Client, when: date) -> str:
        segments = flyer_folder_path(client.drive.subfolder_name or client.company_name, when)
        # A per-client root already scopes by company; don't repeat the name.
        if client.drive.root_folder_id:
            segments = segments[1:]
        return ensure_folder_path(
            self.service,
            self.resolve_root(client),
            segments,
            shared_drive=self.shared,
            cache=self._folder_cache,
        )

    # ---------------------------------------------------------------- uploads

    def find_existing(self, folder_id: str, name: str) -> dict | None:
        escaped = name.replace("'", "\\'")
        kwargs: dict[str, Any] = {
            "q": f"name = '{escaped}' and '{folder_id}' in parents and trashed = false",
            "fields": "files(id, name, appProperties, webViewLink)",
            "pageSize": 5,
            "spaces": "drive",
        }
        if self.shared:
            kwargs.update(supportsAllDrives=True, includeItemsFromAllDrives=True)
        files = self.service.files().list(**kwargs).execute().get("files", [])
        return files[0] if files else None

    def upload_file(
        self,
        path: Path,
        folder_id: str,
        checksum: str = "",
        description: str = "",
    ) -> tuple[str, str]:
        """Upload or replace one file. Returns ``(file_id, web_view_link)``."""
        if not path.exists():
            raise DriveError(f"Cannot upload missing file: {path}")

        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
        existing = self.find_existing(folder_id, path.name)

        if existing and checksum and existing.get("appProperties", {}).get("sha256") == checksum:
            log.info("Skipping %s - identical file already in Drive", path.name)
            return existing["id"], existing.get("webViewLink", "")

        metadata: dict[str, Any] = {
            "name": path.name,
            "description": description[:1000],
            "appProperties": {"sha256": checksum, "source": "flyer-generator"},
        }

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            media = MediaFileUpload(str(path), mimetype=mime, resumable=False)
            try:
                if existing:
                    result = (
                        self.service.files()
                        .update(
                            fileId=existing["id"],
                            body=metadata,
                            media_body=media,
                            fields="id, webViewLink",
                            **({"supportsAllDrives": True} if self.shared else {}),
                        )
                        .execute()
                    )
                    log.info("Replaced %s in Drive", path.name)
                else:
                    result = (
                        self.service.files()
                        .create(
                            body={**metadata, "parents": [folder_id]},
                            media_body=media,
                            fields="id, webViewLink",
                            **({"supportsAllDrives": True} if self.shared else {}),
                        )
                        .execute()
                    )
                    log.info("Uploaded %s to Drive", path.name)
                return result["id"], result.get("webViewLink", "")
            except HttpError as exc:
                last_error = exc
                status = getattr(exc.resp, "status", 0)
                if status not in (403, 429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS:
                    raise DriveError(f"Drive upload of {path.name} failed: {exc}") from exc
                delay = min(2**attempt, 20) + random.uniform(0, 1.0)
                log.warning(
                    "Drive upload of %s failed with %s - retry %d/%d in %.1fs",
                    path.name,
                    status,
                    attempt,
                    MAX_ATTEMPTS,
                    delay,
                )
                time.sleep(delay)
            except Exception as exc:  # network-level failures
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    raise DriveError(f"Drive upload of {path.name} failed: {exc}") from exc
                time.sleep(min(2**attempt, 20))

        raise DriveError(f"Drive upload of {path.name} failed: {last_error}")

    def upload_bytes(
        self,
        data: bytes,
        name: str,
        folder_id: str,
        mime: str = "image/png",
        checksum: str = "",
        description: str = "",
    ) -> tuple[str, str]:
        """Upload straight from memory, so no local file need ever exist.

        This is what makes ``--drive-only`` possible: the renderer hands over a
        buffer and the flyer goes to Drive without touching the disk.
        """
        import io

        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaIoBaseUpload

        existing = self.find_existing(folder_id, name)
        if existing and checksum and existing.get("appProperties", {}).get("sha256") == checksum:
            log.info("Skipping %s - identical file already in Drive", name)
            return existing["id"], existing.get("webViewLink", "")

        metadata: dict[str, Any] = {
            "name": name,
            "description": description[:1000],
            "appProperties": {"sha256": checksum, "source": "flyer-generator"},
        }

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
            try:
                shared = {"supportsAllDrives": True} if self.shared else {}
                if existing:
                    result = (
                        self.service.files()
                        .update(
                            fileId=existing["id"],
                            body=metadata,
                            media_body=media,
                            fields="id, webViewLink",
                            **shared,
                        )
                        .execute()
                    )
                else:
                    result = (
                        self.service.files()
                        .create(
                            body={**metadata, "parents": [folder_id]},
                            media_body=media,
                            fields="id, webViewLink",
                            **shared,
                        )
                        .execute()
                    )
                log.info("Uploaded %s to Drive (%d KB, no local copy)", name, len(data) // 1024)
                return result["id"], result.get("webViewLink", "")
            except HttpError as exc:
                last_error = exc
                status = getattr(exc.resp, "status", 0)
                if status not in (403, 429, 500, 502, 503, 504) or attempt == MAX_ATTEMPTS:
                    raise DriveError(f"Drive upload of {name} failed: {exc}") from exc
                time.sleep(min(2**attempt, 20) + random.uniform(0, 1.0))
            except Exception as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    raise DriveError(f"Drive upload of {name} failed: {exc}") from exc
                time.sleep(min(2**attempt, 20))

        raise DriveError(f"Drive upload of {name} failed: {last_error}")


def upload_flyer_result(
    result: FlyerResult,
    client: Client,
    when: date,
    uploader: DriveUploader | None = None,
) -> FlyerResult:
    """Upload one flyer plus its metadata sidecar. Mutates and returns ``result``."""
    uploader = uploader or DriveUploader()
    folder_id = uploader.target_folder(client, when)

    from ..assets.image_utils import file_sha256

    image_path = Path(result.image_path)
    checksum = file_sha256(image_path) if image_path.exists() else ""
    description = (
        f"{client.company_name} | {result.spec.campaign_id} | "
        f"{result.spec.text.headline} | QA {result.qa_score}"
    )
    file_id, link = uploader.upload_file(image_path, folder_id, checksum, description)
    result.drive_file_id = file_id
    result.drive_url = link

    if result.metadata_path:
        meta_path = Path(result.metadata_path)
        if meta_path.exists():
            uploader.upload_file(meta_path, folder_id, file_sha256(meta_path), description)

    return result
