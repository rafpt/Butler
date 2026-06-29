#!/bin/zsh
set -euo pipefail

DESTINATION="$HOME/Library/LaunchAgents/com.butler.breach-consumer.plist"
launchctl bootout "gui/$UID" "$DESTINATION" 2>/dev/null || true
rm -f "$DESTINATION"
echo "Removed com.butler.breach-consumer"
