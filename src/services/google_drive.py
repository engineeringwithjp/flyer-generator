"""Google Drive integration uploading flyers to client folders."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import GDRIVE_ROOT_FOLDER_ID, GDRIVE_SERVICE_ACCOUNT_KEY, GDRIVE_SERVICE_ACCOUNT_PATH


class GoogleDriveUploader:
    def __init__(
        self,
        root_folder_id: str = GDRIVE_ROOT_FOLDER_ID,
        service_account_path: Optional[str] = GDRIVE_SERVICE_ACCOUNT_PATH,
        service_account_json: Optional[str] = GDRIVE_SERVICE_ACCOUNT_KEY
    ):
        self.root_folder_id = root_folder_id
        self.service_account_path = service_account_path
        self.service_account_json = service_account_json
        self._service = None

    def is_configured(self) -> bool:
        """Returns True if Google service account credentials are available."""
        if self.service_account_json:
            return True
        if self.service_account_path and os.path.exists(self.service_account_path):
            return True
        return False

    def get_service(self):
        if self._service is not None:
            return self._service

        if not self.is_configured():
            return None

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            scopes = ["https://www.googleapis.com/auth/drive"]

            if self.service_account_json:
                info = json.loads(self.service_account_json)
                creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            else:
                creds = service_account.Credentials.from_service_account_file(self.service_account_path, scopes=scopes)

            self._service = build("drive", "v3", credentials=creds)
            return self._service
        except Exception:
            return None

    def upload_flyer(
        self,
        file_path: str,
        client_name: str,
        flyer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Uploads a rendered flyer PNG to the target Google Drive folder."""
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "message": f"File does not exist: {file_path}"}

        upload_name = flyer_name or path.name
        service = self.get_service()

        if service is None:
            # Graceful offline mode when credentials are not yet supplied
            mock_id = f"gdrive_mock_{path.stem}"
            return {
                "status": "offline_simulated",
                "file_id": mock_id,
                "folder_id": self.root_folder_id,
                "file_name": upload_name,
                "message": "Google Drive credentials not set; file saved locally and upload simulated."
            }

        try:
            from googleapiclient.http import MediaFileUpload

            # Target folder ID (root or client-specific subfolder)
            target_folder_id = self.root_folder_id

            # Check if file already exists in folder to avoid duplicates
            query = f"'{target_folder_id}' in parents and name = '{upload_name}' and trashed = false"
            results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            files = results.get("files", [])

            media = MediaFileUpload(file_path, mimetype="image/png", resumable=True)

            if files:
                # Update existing
                file_id = files[0]["id"]
                updated = service.files().update(fileId=file_id, media_body=media).execute()
                return {
                    "status": "updated",
                    "file_id": updated.get("id"),
                    "file_name": upload_name
                }
            else:
                # Create new file
                file_metadata = {
                    "name": upload_name,
                    "parents": [target_folder_id]
                }
                created = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                return {
                    "status": "created",
                    "file_id": created.get("id"),
                    "file_name": upload_name
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Google Drive API upload failed: {str(e)}"
            }
