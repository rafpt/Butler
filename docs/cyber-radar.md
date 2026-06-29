# Cyber Radar operations

## Runtime

- Schedule: daily at 07:30 local time (`Europe/Lisbon`).
- LaunchAgent: `com.butler.cyber-radar`.
- State: `~/Library/Application Support/Butler/butler.db`.
- Reports: `~/Library/Application Support/Butler/reports/radar`.
- Logs: `~/Library/Logs/Butler/cyber-radar.*.log`.
- Model: local OMLX at `http://127.0.0.1:8000/v1`.

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

## Failure behavior

- One source failure marks the report degraded but does not stop publication.
- OMLX failure replaces the synthesis with a deterministic notice.
- A process lock prevents overlapping runs.
- Scheduled runs never inspect cloud-provider settings.
- HTTP sources are HTTPS-only, host-allowlisted, bounded to 2 MiB, and retried with backoff and
  jitter.

## Source policy

Primary sources support factual claims. Discovery feeds may identify a topic but should not be
treated as independent confirmation. HTML indices are never followed automatically; they supply
citations for later review. LinkedIn and YouTube authenticated scraping are outside v1.
