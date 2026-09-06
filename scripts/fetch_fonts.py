#!/usr/bin/env python3
"""Download the brand typefaces into ``assets/fonts/``.

Barlow Condensed and Lato are All Elite's website faces; Anton is a fallback
display face. All are SIL Open Font License, fetched from the official Google
Fonts repository.

Fonts are gitignored - CI runs this as a cached step, and the renderer falls
back to system fonts if it cannot run.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"
BASE = "https://raw.githubusercontent.com/google/fonts/main"

FONTS: dict[str, str] = {
    "BarlowCondensed-Bold.ttf": f"{BASE}/ofl/barlowcondensed/BarlowCondensed-Bold.ttf",
    "BarlowCondensed-SemiBold.ttf": f"{BASE}/ofl/barlowcondensed/BarlowCondensed-SemiBold.ttf",
    "BarlowCondensed-Medium.ttf": f"{BASE}/ofl/barlowcondensed/BarlowCondensed-Medium.ttf",
    "Lato-Regular.ttf": f"{BASE}/ofl/lato/Lato-Regular.ttf",
    "Lato-Bold.ttf": f"{BASE}/ofl/lato/Lato-Bold.ttf",
    "Lato-Black.ttf": f"{BASE}/ofl/lato/Lato-Black.ttf",
    "Anton-Regular.ttf": f"{BASE}/ofl/anton/Anton-Regular.ttf",
    "Oswald-Bold.ttf": f"{BASE}/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "Archivo-Black.ttf": f"{BASE}/ofl/archivoblack/ArchivoBlack-Regular.ttf",
    "Inter-Regular.ttf": f"{BASE}/ofl/inter/Inter%5Bopsz,wght%5D.ttf",
    "PlayfairDisplay-Bold.ttf": f"{BASE}/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
}

TIMEOUT = 30


def fetch(name: str, url: str) -> bool:
    target = FONTS_DIR / name
    if target.exists() and target.stat().st_size > 1000:
        print(f"  = {name} (already present)")
        return True
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "flyer-generator"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  ! {name}: {exc}")
        return False
    if len(data) < 1000:
        print(f"  ! {name}: response too small ({len(data)} bytes)")
        return False
    target.write_bytes(data)
    print(f"  + {name} ({len(data) // 1024} KB)")
    return True


def main() -> int:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(FONTS)} font file(s) into {FONTS_DIR.relative_to(ROOT)}")
    ok = sum(fetch(name, url) for name, url in FONTS.items())
    print(f"\n{ok}/{len(FONTS)} font(s) available.")
    if ok == 0:
        print(
            "No fonts downloaded. The renderer will fall back to system fonts, "
            "which still works but looks less polished.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
