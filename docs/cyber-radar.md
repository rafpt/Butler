# Cyber Radar operations

## Runtime

- Schedule: daily at 07:30 local time (`Europe/Lisbon`).
- LaunchAgent: `com.butler.cyber-radar`.
- State: `~/Library/Application Support/Butler/butler.db`.
- Reports: `~/Library/Application Support/Butler/reports/radar`.
- Logs: `~/Library/Logs/Butler/cyber-radar.*.log`.
- Model: local OMLX at `http://127.0.0.1:8000/v1`.
- Notifications: macOS and `@butleradelaidebot` when configured.

## Operator commands

```bash
cd /Users/raf/Code/Butler
uv run butler radar latest
uv run butler radar run --dry-run --no-notify
uv run butler watch list
launchctl print gui/$UID/com.butler.cyber-radar
```

Use `scripts/install_launch_agent.sh` after changing the plist template or Python environment.
Use `scripts/uninstall_launch_agent.sh` to remove the schedule without deleting reports.

## Telegram alerts

The dedicated bot is
[`@butleradelaidebot`](https://t.me/butleradelaidebot). Open it, send `/start`, then run:

```bash
./scripts/configure_telegram.sh
uv run butler notify telegram-chats
uv run butler notify telegram-test
```

The script stores `bot-token` and `chat-id` as generic-password entries in macOS Keychain under
the service `com.butler.telegram`. Environment variables
`BUTLER_TELEGRAM_BOT_TOKEN` and `BUTLER_TELEGRAM_CHAT_ID` remain available for ephemeral
development only. Neither secret is written to Git, SQLite, logs, reports, or the LaunchAgent
plist.

Telegram failures are isolated from macOS notifications and never prevent report publication.
Reports containing `Must` items include stronger wording and up to three primary-source links.

## Failure behavior

- One source failure marks the report degraded but does not stop publication.
- OMLX failure replaces the synthesis with a deterministic notice.
- A process lock prevents overlapping runs.
- Notification-channel failures are logged but never stop report publication.
- Scheduled runs never inspect cloud-provider settings.
- HTTP sources are HTTPS-only, host-allowlisted, bounded to 2 MiB, and retried with backoff and
  jitter.

## Source policy

Primary sources support factual claims. Discovery feeds may identify a topic but should not be
treated as independent confirmation. HTML indices are never followed automatically; they supply
citations for later review. LinkedIn and YouTube authenticated scraping are outside v1.
