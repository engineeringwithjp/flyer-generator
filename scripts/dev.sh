#!/usr/bin/env bash
# Developer tasks. This used to be a Makefile at the repository root; it moved
# here so the project folder shows nothing but folders in Finder.
#
#   ./scripts/dev.sh install     create .venv and install everything
#   ./scripts/dev.sh preview     render a flyer with no API calls, no upload
#   ./scripts/dev.sh check       lint + tests, what CI runs
#
set -euo pipefail
cd "$(dirname "$0")/.."

VENV=.venv
PY="$VENV/bin/python"

usage() {
  sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
  echo
  echo "targets: install fonts generate preview ingest validate test lint typecheck check clean"
}

case "${1:-help}" in
  install)
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip
    "$VENV/bin/pip" install -e ".[drive,dev]"
    "$PY" scripts/fetch_fonts.py \
      || echo "font download skipped (offline) - bundled fallbacks will be used"
    "$PY" scripts/upscale_logo.py || true
    ;;
  fonts)     "$PY" scripts/fetch_fonts.py ;;
  logo)      "$PY" scripts/upscale_logo.py ;;
  generate)  "$PY" -m app.cli generate ;;
  preview)   FLYER_OFFLINE=1 "$PY" -m app.cli generate --no-upload ;;
  ingest)    "$PY" -m app.cli ingest-reference references/inbox ;;
  intake)    "$PY" -m app.cli intake ;;
  validate)  "$PY" -m app.cli validate ;;
  test)      "$VENV/bin/pytest" -q -m "not integration" ;;
  lint)
    "$VENV/bin/ruff" check app tests scripts
    "$VENV/bin/ruff" format --check app tests scripts
    ;;
  typecheck) "$VENV/bin/mypy" app ;;
  check)
    "$0" lint
    "$0" test
    ;;
  clean)
    rm -rf output/* .pytest_cache .mypy_cache .ruff_cache
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
    ;;
  help|-h|--help) usage ;;
  *) echo "unknown target: $1" >&2; usage; exit 2 ;;
esac
