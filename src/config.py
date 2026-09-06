"""Global configuration and paths for Flyer Generator."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

CLIENTS_DIR = BASE_DIR / "clients"
REFERENCES_DIR = BASE_DIR / "references"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DESIGN_SYSTEM_DIR = DATA_DIR / "design-system"
OUTPUT_DIR = BASE_DIR / "output"
SKILLS_DIR = BASE_DIR / ".claude" / "skills" / "construction-flyer"

# Simple .env loader
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

# Environment variables
GDRIVE_ROOT_FOLDER_ID = os.getenv("GDRIVE_ROOT_FOLDER_ID", "12Ho15EiJumnZkSAPm0I1Zd9Vwe6CuLiT")
GDRIVE_SERVICE_ACCOUNT_PATH = os.getenv("GDRIVE_SERVICE_ACCOUNT_PATH", "service_account.json")
GDRIVE_SERVICE_ACCOUNT_KEY = os.getenv("GDRIVE_SERVICE_ACCOUNT_KEY")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
CANVA_API_KEY = os.getenv("CANVA_API_KEY")
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN")
MOBBIN_API_KEY = os.getenv("MOBBIN_API_KEY")

DEFAULT_CLIENT = os.getenv("DEFAULT_CLIENT", "all-elite")
DAILY_FLYER_COUNT = int(os.getenv("DAILY_FLYER_COUNT", "2"))

# Visual Canvas Constants
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350
ASPECT_RATIO = "4:5"
SAFE_MARGIN_X = 72
SAFE_MARGIN_Y = 80
BRAND_ACCENT_DEFAULT = "#80272B"
DARK_NEUTRAL_DEFAULT = "#1C1C1E"
LIGHT_NEUTRAL_DEFAULT = "#FFFFFF"
