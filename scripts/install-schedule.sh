#!/usr/bin/env bash
# Run the daily flyer job on this Mac, via launchd.
#
# Why not GitHub Actions? The workflow exists and works, but it runs on a cloud
# runner that has no access to your Google Drive for Desktop mount. Delivering
# from there needs Google Drive API credentials stored as repository secrets -
# an OAuth flow you would have to complete yourself. On this Mac the mount is
# already there and already authenticated, so there is nothing to set up.
#
#   ./scripts/install-schedule.sh            install, 10:07 on weekdays
#   ./scripts/install-schedule.sh --at 08:30 a different time
#   ./scripts/install-schedule.sh --uninstall
#
# launchd catches up on a missed run when the Mac wakes, so a closed lid delays
# the flyers rather than skipping the day.

set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

LABEL="com.nedatechnologies.flyer-generator"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
AT="10:07"
DAYS=(1 2 3 4 5)   # Monday to Friday

while [ $# -gt 0 ]; do
  case "$1" in
    --at) AT="$2"; shift 2 ;;
    --daily) DAYS=(0 1 2 3 4 5 6); shift ;;
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

{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
  echo '<plist version="1.0"><dict>'
  echo "  <key>Label</key><string>$LABEL</string>"
  echo '  <key>ProgramArguments</key><array>'
  echo "    <string>$REPO/.venv/bin/python</string>"
  echo '    <string>-m</string><string>app.cli</string><string>generate</string>'
  echo '  </array>'
  echo "  <key>WorkingDirectory</key><string>$REPO</string>"
  echo '  <key>StartCalendarInterval</key><array>'
  for day in "${DAYS[@]}"; do
    echo "    <dict><key>Weekday</key><integer>$day</integer>"
    echo "      <key>Hour</key><integer>$HOUR</integer>"
    echo "      <key>Minute</key><integer>$MINUTE</integer></dict>"
  done
  echo '  </array>'
  # Run a missed slot when the Mac wakes, rather than skipping the day.
  echo '  <key>RunAtLoad</key><false/>'
  echo "  <key>StandardOutPath</key><string>$REPO/output/logs/schedule.log</string>"
  echo "  <key>StandardErrorPath</key><string>$REPO/output/logs/schedule.log</string>"
  echo '  <key>ProcessType</key><string>Background</string>'
  echo '</dict></plist>'
} > "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Installed: flyers at $AT on $( [ ${#DAYS[@]} -eq 7 ] && echo "every day" || echo "weekdays" )."
echo "  log:      $REPO/output/logs/schedule.log"
echo "  check:    launchctl list | grep flyer-generator"
echo "  run now:  launchctl kickstart -k gui/$(id -u)/$LABEL"
echo "  remove:   ./scripts/install-schedule.sh --uninstall"
