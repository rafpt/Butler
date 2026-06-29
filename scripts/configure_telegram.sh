#!/bin/zsh
set -euo pipefail

SERVICE="com.butler.telegram"
ROOT="${0:A:h:h}"

echo "Existing Telegram bot: @Aspasia_4U_Bot"
echo "Source: /Users/raf/Code/aspasia_bot"
echo "Use only the current token obtained from BotFather; never reuse a token found in Git history."
echo
echo "The macOS Keychain will securely prompt for the BotFather token."
/usr/bin/security add-generic-password \
  -U \
  -a "bot-token" \
  -s "$SERVICE" \
  -l "Butler Telegram bot token" \
  -w

if /usr/bin/security find-generic-password \
  -s "$SERVICE" \
  -a "chat-id" >/dev/null 2>&1; then
  echo
  echo "Existing Butler chat ID found in macOS Keychain; reusing it."
else
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
fi

echo
echo "Credentials stored in macOS Keychain. Sending a test alert..."
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/butler" ]]; then
  "$ROOT/.venv/bin/butler" notify telegram-test
else
  PYTHONPATH="$ROOT/src" python3 -m butler notify telegram-test
fi
