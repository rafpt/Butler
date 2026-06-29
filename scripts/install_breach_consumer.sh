#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
TEMPLATE="$ROOT/config/launchd/com.butler.breach-consumer.plist"
DESTINATION="$HOME/Library/LaunchAgents/com.butler.breach-consumer.plist"
DATA_DIR="${BUTLER_DATA_DIR:-$HOME/Library/Application Support/Butler}"
OUTBOX="${BUTLER_SCANNER_OUTBOX_ROOT:-$HOME/Library/Application Support/Data Breach Scanner/outbox}"
LOGS_DIR="$HOME/Library/Logs/Butler"
DOMAIN="gui/$UID"
PYTHON_BIN="${BUTLER_PYTHON:-$ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Butler Python not found: $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "${DESTINATION:h}" "$DATA_DIR" "$OUTBOX/private" "$LOGS_DIR"
sed \
  -e "s|__PYTHON__|$PYTHON_BIN|g" \
  -e "s|__ROOT__|$ROOT|g" \
  -e "s|__DATA__|$DATA_DIR|g" \
  -e "s|__OUTBOX__|$OUTBOX|g" \
  -e "s|__LOGS__|$LOGS_DIR|g" \
  "$TEMPLATE" > "$DESTINATION"

plutil -lint "$DESTINATION"
launchctl bootout "$DOMAIN" "$DESTINATION" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$DESTINATION"
launchctl enable "$DOMAIN/com.butler.breach-consumer"
echo "Installed com.butler.breach-consumer (every 5 minutes)"
