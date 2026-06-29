#!/bin/zsh
set -euo pipefail

SERVICE="com.butler.telegram"
ROOT="${0:A:h:h}"

echo "Telegram bot: @Aspasia_4U_Bot"
echo "Before continuing, open https://t.me/Aspasia_4U_Bot and send /start."
echo
echo "The macOS Keychain will securely prompt for the BotFather token."
/usr/bin/security add-generic-password \
  -U \
  -a "bot-token" \
  -s "$SERVICE" \
  -l "Butler Telegram bot token" \
  -w

echo
echo "Send /start to @Aspasia_4U_Bot now, then press Enter."
read -r
echo "Chats visible to the bot:"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/butler" ]]; then
  "$ROOT/.venv/bin/butler" notify telegram-chats
else
  PYTHONPATH="$ROOT/src" python3 -m butler notify telegram-chats
fi

echo
echo "Now enter the numeric Telegram chat ID when Keychain prompts."
/usr/bin/security add-generic-password \
  -U \
  -a "chat-id" \
  -s "$SERVICE" \
  -l "Butler Telegram chat ID" \
  -w

echo
echo "Credentials stored in macOS Keychain. Sending a test alert..."
if [[ -x "$ROOT/.venv/bin/butler" ]]; then
  "$ROOT/.venv/bin/butler" notify telegram-test
else
  PYTHONPATH="$ROOT/src" python3 -m butler notify telegram-test
fi
