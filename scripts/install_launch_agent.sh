#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
TEMPLATE="$ROOT/config/launchd/com.butler.cyber-radar.plist"
DESTINATION="$HOME/Library/LaunchAgents/com.butler.cyber-radar.plist"
DATA_DIR="${BUTLER_DATA_DIR:-$HOME/Library/Application Support/Butler}"
LOGS_DIR="$HOME/Library/Logs/Butler"
DOMAIN="gui/$UID"

if [[ -n "${BUTLER_PYTHON:-}" ]]; then
  PYTHON_BIN="$BUTLER_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

mkdir -p "${DESTINATION:h}" "$DATA_DIR" "$LOGS_DIR"

sed \
  -e "s|__PYTHON__|$PYTHON_BIN|g" \
  -e "s|__ROOT__|$ROOT|g" \
  -e "s|__DATA__|$DATA_DIR|g" \
  -e "s|__LOGS__|$LOGS_DIR|g" \
  "$TEMPLATE" > "$DESTINATION"

plutil -lint "$DESTINATION"
launchctl bootout "$DOMAIN" "$DESTINATION" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$DESTINATION"
launchctl enable "$DOMAIN/com.butler.cyber-radar"
launchctl print "$DOMAIN/com.butler.cyber-radar" >/dev/null

echo "Installed com.butler.cyber-radar (daily at 07:30 local time)"
echo "Plist: $DESTINATION"
echo "Reports: $DATA_DIR/reports/radar"
