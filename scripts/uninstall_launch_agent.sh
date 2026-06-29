#!/bin/zsh
set -euo pipefail

DESTINATION="$HOME/Library/LaunchAgents/com.butler.cyber-radar.plist"
DOMAIN="gui/$UID"

launchctl bootout "$DOMAIN" "$DESTINATION" 2>/dev/null || true
rm -f "$DESTINATION"
echo "Removed com.butler.cyber-radar"
