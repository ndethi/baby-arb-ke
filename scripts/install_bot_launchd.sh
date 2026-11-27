#!/usr/bin/env bash
# Install (or reinstall) the shop bot as a macOS launch agent so it survives
# logouts, crashes and reboots. Runs `baby-arb bot run` from this working copy,
# which also runs `cal tick` every 5 minutes.
#
#   scripts/install_bot_launchd.sh            install / reload
#   scripts/install_bot_launchd.sh uninstall  stop and remove
#
# The bot runs whatever branch is checked out here, and reads .env from here.
# Only one process may poll the bot token: stop any `baby-arb bot run` first.
set -euo pipefail

LABEL="ke.babyreshop.bot"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/babyreshop"
DOMAIN="gui/$(id -u)"

# bootout returns before the job is gone; bootstrap then fails with error 5.
stop_agent() {
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  for _ in $(seq 1 30); do
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || return 0
    sleep 1
  done
  echo "$LABEL did not stop within 30 s" >&2
  return 1
}

if [[ "${1:-}" == "uninstall" ]]; then
  stop_agent
  rm -f "$PLIST"
  echo "removed $LABEL"
  exit 0
fi

VENV="$(cd "$REPO" && poetry env info --path)"
BIN="$VENV/bin/baby-arb"
[[ -x "$BIN" ]] || { echo "missing $BIN; run poetry install" >&2; exit 1; }
mkdir -p "$LOG_DIR" "$(dirname "$PLIST")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BIN</string>
        <string>bot</string>
        <string>run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$VENV/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <!-- Agents default to throttled disk I/O; startup then took ~2 min instead of seconds. -->
    <key>ProcessType</key>
    <string>Interactive</string>
    <!-- Restart after a crash or error exit; a clean stop (exit 0) stays stopped. -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/bot.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/bot.error.log</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST" >/dev/null
stop_agent
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "installed $LABEL -> $PLIST"
echo "logs: $LOG_DIR/bot.log, $LOG_DIR/bot.error.log"
