#!/usr/bin/env python3
"""Analyse and file design references.

Thin wrapper around `python -m app.cli ingest-reference`, kept because a plain script
path is easier to wire into cron, Automator or a shortcut than a module path.
Every argument is forwarded.
"""

from __future__ import annotations

import sys

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["ingest-reference", *sys.argv[1:]]))
