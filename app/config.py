"""Application settings, loaded once from the environment.

Nothing else in the codebase reads ``os.environ`` for application config, so
swapping models, canvas sizes or Drive targets is a one-file change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigurationError

# Repository root = two levels up from this file (app/config.py -> app -> root).
# ``FLYER_ROOT`` overrides it, which is how tests run against a temporary
# repository and how CI can point at a checked-out working copy.
DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    override = os.getenv("FLYER_ROOT")
    return Path(override).expanduser().resolve() if override else DEFAULT_ROOT


ROOT = DEFAULT_ROOT


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - operator error
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Paths:
    """Every path the application touches, derived from one root."""

    root: Path

    @property
    def app(self) -> Path:
        return self.root / "app"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def clients(self) -> Path:
        return self.root / "clients"

    @property
    def references(self) -> Path:
        return self.root / "references"

    @property
    def reference_inbox(self) -> Path:
        return self.references / "inbox"

    @property
    def reference_approved(self) -> Path:
        return self.references / "approved"

    @property
    def reference_experimental(self) -> Path:
        return self.references / "experimental"

    @property
    def reference_rejected(self) -> Path:
        return self.references / "rejected"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def fonts(self) -> Path:
        return self.assets / "fonts"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def design_system(self) -> Path:
        return self.root / "design-system"

    @property
    def skill(self) -> Path:
        return self.root / ".claude" / "skills" / "construction-flyer"

    @property
    def reference_index(self) -> Path:
        return self.data / "references" / "index.json"

    @property
    def asset_index(self) -> Path:
        return self.data / "assets" / "index.json"

    @property
    def history_dir(self) -> Path:
        return self.data / "generation-history"

    @property
    def history_index(self) -> Path:
        return self.history_dir / "history.json"

    def ensure(self) -> None:
        for path in (
            self.reference_inbox,
            self.reference_approved,
            self.reference_experimental,
            self.reference_rejected,
            self.assets,
            self.fonts,
            self.output,
            self.history_dir,
            self.reference_index.parent,
            self.asset_index.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    # --- Claude ---
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_vision_model: str
    anthropic_max_retries: int

    # --- Google Drive ---
    google_client_id: str | None
    google_client_secret: str | None
    google_refresh_token: str | None
    google_service_account_file: str | None
    drive_root_folder_id: str | None
    drive_is_shared_drive: bool
    drive_local_path: str | None

    # --- Defaults ---
    default_client: str
    default_flyer_count: int
    schedule_timezone: str
    schedule_time: str
    schedule_mode: str
    schedule_interval_hours: int
    schedule_window: str
    schedule_days: str
    output_width: int
    output_height: int
    output_format: str

    # --- disk hygiene ---
    asset_max_edge: int
    asset_reuse_days: int
    photo_grade: str
    output_retention_days: int
    delete_after_upload: bool

    offline: bool
    log_level: str

    paths: Paths = field(default_factory=lambda: Paths(root=repo_root()))

    # ------------------------------------------------------------------

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key) and not self.offline

    @property
    def drive_local_enabled(self) -> bool:
        from pathlib import Path as _Path

        path = self.drive_local_path
        if not path:
            return False
        return _Path(path).expanduser().is_dir()

    @property
    def drive_enabled(self) -> bool:
        if not self.drive_root_folder_id:
            return False
        has_oauth = all(
            (self.google_client_id, self.google_client_secret, self.google_refresh_token)
        )
        return bool(has_oauth or self.google_service_account_file)

    def require_claude(self) -> str:
        if self.offline:
            raise ConfigurationError("FLYER_OFFLINE=1 - Claude calls are disabled.")
        if not self.anthropic_api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set. Add it to .env locally, or as a GitHub "
                "Actions secret named ANTHROPIC_API_KEY."
            )
        return self.anthropic_api_key

    def describe(self) -> dict[str, object]:
        """Safe-to-log summary. Never includes secret values."""
        return {
            "model": self.anthropic_model,
            "vision_model": self.anthropic_vision_model,
            "claude_enabled": self.claude_enabled,
            "drive_enabled": self.drive_enabled,
            "drive_local": self.drive_local_enabled,
            "default_client": self.default_client,
            "default_flyer_count": self.default_flyer_count,
            "canvas": f"{self.output_width}x{self.output_height}",
            "timezone": self.schedule_timezone,
            "offline": self.offline,
        }


def load_settings(env_file: Path | None = None) -> Settings:
    """Read settings from the environment, optionally seeded by a .env file."""
    root = repo_root()
    load_dotenv(env_file or (root / ".env"), override=False)

    def _clean(name: str) -> str | None:
        value = os.getenv(name)
        value = value.strip() if value else ""
        return value or None

    settings = Settings(
        anthropic_api_key=_clean("ANTHROPIC_API_KEY"),
        anthropic_model=_clean("ANTHROPIC_MODEL") or "claude-opus-5",
        anthropic_vision_model=_clean("ANTHROPIC_VISION_MODEL")
        or _clean("ANTHROPIC_MODEL")
        or "claude-sonnet-5",
        anthropic_max_retries=_int("ANTHROPIC_MAX_RETRIES", 4),
        google_client_id=_clean("GOOGLE_CLIENT_ID"),
        google_client_secret=_clean("GOOGLE_CLIENT_SECRET"),
        google_refresh_token=_clean("GOOGLE_REFRESH_TOKEN"),
        google_service_account_file=_clean("GOOGLE_SERVICE_ACCOUNT_FILE"),
        drive_root_folder_id=_clean("GOOGLE_DRIVE_ROOT_FOLDER_ID"),
        drive_is_shared_drive=_bool("GOOGLE_DRIVE_IS_SHARED_DRIVE"),
        # Google Drive for Desktop mount. When set, flyers are written straight
        # into Drive and never land in the project folder.
        drive_local_path=_clean("DRIVE_LOCAL_PATH"),
        default_client=_clean("DEFAULT_CLIENT") or "all-elite",
        default_flyer_count=_int("DEFAULT_FLYER_COUNT", 2),
        schedule_timezone=_clean("SCHEDULE_TIMEZONE") or "America/New_York",
        schedule_time=_clean("SCHEDULE_TIME") or "10:07",
        schedule_mode=(_clean("SCHEDULE_MODE") or "daily").lower(),
        schedule_interval_hours=_int("SCHEDULE_INTERVAL_HOURS", 3),
        schedule_window=_clean("SCHEDULE_WINDOW") or "08:00-20:00",
        schedule_days=(_clean("SCHEDULE_DAYS") or "mon-fri").lower(),
        # 2160x2700 is the same 4:5 frame Instagram wants, at twice the linear
        # resolution of the old 1080x1350. The source photography is 4056px
        # wide, so this is still a downscale - nothing is being invented - but
        # the flyer now holds up full-screen on a retina display and prints
        # cleanly at 7x9in / 300dpi, which the 1080px version did not.
        output_width=_int("OUTPUT_WIDTH", 2160),
        output_height=_int("OUTPUT_HEIGHT", 2700),
        output_format=(_clean("OUTPUT_FORMAT") or "PNG").upper(),
        # Must stay above the canvas long edge with room for a focal crop,
        # otherwise the library becomes the resolution ceiling.
        asset_max_edge=_int("ASSET_MAX_EDGE", 3600),
        # A photograph that has gone out to the client is not used again for
        # this many days. Raise it as the library grows; lower it only if runs
        # start coming up short.
        asset_reuse_days=_int("ASSET_REUSE_DAYS", 21),
        # Finishing recipe applied to every photograph: "house", "light" or
        # "none". See app/rendering/finishing.py.
        photo_grade=(_clean("PHOTO_GRADE") or "house").lower(),
        output_retention_days=_int("OUTPUT_RETENTION_DAYS", 7),
        delete_after_upload=_bool("DELETE_AFTER_UPLOAD"),
        offline=_bool("FLYER_OFFLINE"),
        log_level=_clean("LOG_LEVEL") or "INFO",
        paths=Paths(root=root),
    )
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    """Drop cached settings. Used by tests and by long-lived processes."""
    get_settings.cache_clear()


def load_json_config(name: str) -> dict:
    """Load one of the JSON files in ``config/``."""
    import json

    path = repo_root() / "config" / name
    if not path.exists():
        raise ConfigurationError(f"Missing config file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{path} is not valid JSON: {exc}") from exc
