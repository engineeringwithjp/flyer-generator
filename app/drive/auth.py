"""Google Drive authentication.

Two credential styles are supported:

* **OAuth refresh token** (recommended). Files land in *your* My Drive and count
  against your quota. Mint one locally with ``python scripts/google_oauth_setup.py``
  and store the three values as GitHub secrets.
* **Service account**. Only useful with a Shared Drive - a service account has
  no My Drive storage quota of its own.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from ..errors import DriveError
from ..logging_setup import get_logger

log = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def drive_available(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.drive_enabled:
        return False
    try:
        import google.auth  # noqa: F401
        import googleapiclient  # noqa: F401
    except ImportError:
        log.warning(
            "Drive is configured but the client libraries are missing. "
            "Install with: pip install -e '.[drive]'"
        )
        return False
    return True


def build_credentials(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()

    if settings.google_refresh_token:
        if not (settings.google_client_id and settings.google_client_secret):
            raise DriveError(
                "GOOGLE_REFRESH_TOKEN is set but GOOGLE_CLIENT_ID / "
                "GOOGLE_CLIENT_SECRET are missing."
            )
        try:
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise DriveError("pip install -e '.[drive]' to enable Google Drive") from exc

        return Credentials(
            token=None,
            refresh_token=settings.google_refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )

    if settings.google_service_account_file:
        try:
            from google.oauth2 import service_account
        except ImportError as exc:
            raise DriveError("pip install -e '.[drive]' to enable Google Drive") from exc

        path = settings.paths.root / settings.google_service_account_file
        candidate = path if path.exists() else None
        if candidate is None:
            from pathlib import Path

            direct = Path(settings.google_service_account_file)
            candidate = direct if direct.exists() else None
        if candidate is None:
            raise DriveError(
                f"Service-account file not found: {settings.google_service_account_file}"
            )
        return service_account.Credentials.from_service_account_file(str(candidate), scopes=SCOPES)

    raise DriveError(
        "No Google credentials configured. Set GOOGLE_CLIENT_ID / "
        "GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN, or GOOGLE_SERVICE_ACCOUNT_FILE."
    )


def build_drive_service(settings: Settings | None = None) -> Any:
    settings = settings or get_settings()
    credentials = build_credentials(settings)
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise DriveError("pip install -e '.[drive]' to enable Google Drive") from exc

    try:
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        raise DriveError(f"Could not build the Drive client: {exc}") from exc
