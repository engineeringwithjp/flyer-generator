#!/usr/bin/env bash
# Run the daily flyer job on this Mac, via launchd.
#
#   ./scripts/install-schedule.sh            install, 10:00 AM daily
#   ./scripts/install-schedule.sh --at 10:00 a different time
#   ./scripts/install-schedule.sh --uninstall
#
# launchd catches up on a missed run when the Mac wakes, so a closed lid delays
# the flyers rather than skipping the day.

set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

LABEL="com.nedatechnologies.flyer-generator"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
AT="10:00"

while [ $# -gt 0 ]; do
  case "$1" in
    --at) AT="$2"; shift 2 ;;
    --wake)
      echo "Configuring macOS hardware wake for 09:59 AM daily..."
      sudo pmset repeat wakeorpoweron MTWRFSU 09:59:00 || true
      shift
      ;;
    --uninstall)
      launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
      rm -f "$PLIST"
      echo "Removed the daily flyer job."
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

HOUR="${AT%%:*}"
MINUTE="${AT##*:}"
HOUR="${HOUR#0}"; MINUTE="${MINUTE#0}"
: "${HOUR:=0}"; : "${MINUTE:=0}"

mkdir -p "$HOME/Library/LaunchAgents" "$REPO/output/logs"

cat << PLIST_CONTENT > "$PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$REPO/.venv/bin/python</string>
    <string>-m</string><string>app.cli</string><string>daily</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$REPO/output/logs/schedule.log</string>
  <key>StandardErrorPath</key><string>$REPO/output/logs/schedule.log</string>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
PLIST_CONTENT

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || launchctl load "$PLIST"

echo "Installed $LABEL: runs every day at $AT."
echo "Note: To wake this Mac from hardware sleep at 09:59 AM, run: ./scripts/install-schedule.sh --wake"
