#!/usr/bin/env python3
"""Mint a Google Drive refresh token for unattended uploads.

Run this once on your own machine. It opens a browser, you approve access, and
it prints three values to put into GitHub Secrets. Nothing is written to disk
and nothing is committed.

    python scripts/google_oauth_setup.py --client-secrets ~/Downloads/client_secret.json

Getting the client secrets file:

  1. console.cloud.google.com -> create (or pick) a project
  2. APIs & Services -> Library -> enable "Google Drive API"
  3. APIs & Services -> OAuth consent screen -> External -> add yourself as a
     test user
  4. Credentials -> Create credentials -> OAuth client ID -> Desktop app
  5. Download the JSON

Why OAuth rather than a service account: a service account has no My Drive
storage quota of its own, so uploads into a normal Drive folder fail. With a
refresh token the files land in your Drive, owned by you.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="Path to the OAuth client JSON downloaded from Google Cloud",
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install the Drive extras first:\n\n    pip install -e '.[drive]'\n", file=sys.stderr)
        return 1

    path = Path(args.client_secrets).expanduser()
    if not path.exists():
        print(f"No such file: {path}", file=sys.stderr)
        return 1

    payload = json.loads(path.read_text())
    section = payload.get("installed") or payload.get("web") or {}
    client_id = section.get("client_id", "")
    client_secret = section.get("client_secret", "")
    if not client_id:
        print("That JSON does not look like an OAuth client file.", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
    credentials = flow.run_local_server(port=args.port, prompt="consent", access_type="offline")

    if not credentials.refresh_token:
        print(
            "\nGoogle did not return a refresh token. Revoke the app's access at "
            "https://myaccount.google.com/permissions and run this again.",
            file=sys.stderr,
        )
        return 1

    print("\n" + "=" * 68)
    print("Add these three as GitHub repository secrets")
    print("  Settings -> Secrets and variables -> Actions -> New repository secret")
    print("=" * 68)
    print(f"\nGOOGLE_CLIENT_ID\n  {client_id}")
    print(f"\nGOOGLE_CLIENT_SECRET\n  {client_secret}")
    print(f"\nGOOGLE_REFRESH_TOKEN\n  {credentials.refresh_token}")
    print("\nAnd for local use, put the same three in .env (which is gitignored).")
    print("\nDo not paste these into an issue, a commit or a chat window.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
