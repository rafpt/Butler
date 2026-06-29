#!/bin/zsh
set -euo pipefail

SERVICE="com.butler.telegram"
ROOT="${0:A:h:h}"

echo "Telegram alert bot: @butleradelaidebot"
echo "Use only the current token obtained from BotFather; never reuse a token found in Git history."
echo
echo "Quando aparecer 'password data', cole APENAS o token do BotFather."
echo "Não introduza a password do Mac e não cole um URL."
echo "Formato esperado: 123456789:AA..."
/usr/bin/security add-generic-password \
  -U \
  -a "bot-token" \
  -s "$SERVICE" \
  -l "Butler Telegram bot token" \
  -w

TOKEN=$(/usr/bin/security find-generic-password -s "$SERVICE" -a "bot-token" -w)
if [[ ! "$TOKEN" =~ '^[0-9]{8,12}:[A-Za-z0-9_-]{30,}$' ]]; then
  /usr/bin/security delete-generic-password \
    -s "$SERVICE" \
    -a "bot-token" >/dev/null
  unset TOKEN
  echo "ERRO: token BotFather inválido; o valor foi removido do Keychain." >&2
  exit 1
fi
curl --fail --silent --show-error \
  "https://api.telegram.org/bot${TOKEN}/deleteWebhook" \
  --data "drop_pending_updates=false" >/dev/null
unset TOKEN
echo "Webhook removed: this bot is outbound-only and has no resident receiver."

if /usr/bin/security find-generic-password \
  -s "$SERVICE" \
  -a "chat-id" >/dev/null 2>&1; then
  echo
  echo "Existing Butler chat ID found in macOS Keychain; reusing it."
else
  echo
  echo "Send /start to @butleradelaidebot now, then press Enter."
  read -r
  echo "Chats visible to the bot:"
  cd "$ROOT"
  if [[ -x "$ROOT/.venv/bin/butler" ]]; then
    "$ROOT/.venv/bin/butler" notify telegram-chats
  else
    PYTHONPATH="$ROOT/src" python3 -m butler notify telegram-chats
  fi

  echo
  echo "Quando aparecer 'password data', cole o chat ID numérico mostrado acima."
  echo "Não introduza a password do Mac."
  /usr/bin/security add-generic-password \
    -U \
    -a "chat-id" \
    -s "$SERVICE" \
    -l "Butler Telegram chat ID" \
    -w
  CHAT_ID=$(/usr/bin/security find-generic-password -s "$SERVICE" -a "chat-id" -w)
  if [[ ! "$CHAT_ID" =~ '^-?[0-9]+$' ]]; then
    /usr/bin/security delete-generic-password \
      -s "$SERVICE" \
      -a "chat-id" >/dev/null
    unset CHAT_ID
    echo "ERRO: chat ID inválido; o valor foi removido do Keychain." >&2
    exit 1
  fi
  unset CHAT_ID
fi

echo
echo "Credentials stored in macOS Keychain. Sending a test alert..."
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/butler" ]]; then
  "$ROOT/.venv/bin/butler" notify telegram-test
else
  PYTHONPATH="$ROOT/src" python3 -m butler notify telegram-test
fi
