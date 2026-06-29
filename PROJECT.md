# Butler — project charter

## Goal

Build a private, local-first chief of staff for one macOS user. Butler organizes
work, produces actionable cyber intelligence and delivers personal alerts
without exposing private context to public systems.

## Responsibilities

- Personal assistance, planning, research, automation and local operations.
- Daily Cyber Radar at 07:30 Europe/Lisbon.
- Private remediation alerts from Data Breach Scanner.
- Policy-gated actions, durable SQLite state and structured audit logs.
- Local OMLX synthesis; cloud models only for explicitly requested deep dives.

## Boundaries

- Telegram identity: `@butleradelaidebot`.
- Butler reads only `Data Breach Scanner/outbox/private`.
- It never publishes to HiveSec, BASH sites or public Telegram channels.
- It does not hold Aspasia, HiveSec or scanner source credentials.
- `archive/Candy` is legacy reference only and is absent from the active Git tree.
- n8n and Langfuse are not runtime dependencies for v1.

## Implemented changes — 2026-06-29

- Replaced Candy with a clean modular Butler codebase.
- Added the Cyber Radar domain, SQLite migrations, source adapters, deterministic
  ranking, feedback/watchlists and OMLX degraded-mode reporting.
- Added CLI commands for radar, watchlists, feedback and deep research.
- Added the `butler-cyber-radar` Codex skill and daily launchd job.
- Migrated Telegram identity to `@butleradelaidebot` with Keychain storage and
  identity verification.
- Removed HiveSec/Grok/public publishing responsibilities from Butler.
- Added a strict private breach-event consumer with 64 KiB limits, schema
  validation, symlink rejection and move-after-confirmed-delivery semantics.
- Added a five-minute launchd consumer and tests for success, failure and
  private/public boundary enforcement.

## Operations

```bash
make check
uv run butler health
uv run butler radar run --dry-run
uv run butler breach consume --dry-run
launchctl print gui/$UID/com.butler.cyber-radar
launchctl print gui/$UID/com.butler.breach-consumer
```

Runtime data is under `~/Library/Application Support/Butler`; secrets remain in
the `com.butler.telegram` Keychain service.

## Success criteria

- A daily report is available by 07:40 even when sources or OMLX fail.
- Scheduled execution makes no cloud-model call.
- Every factual radar item retains source provenance.
- Personal exposure events reach only the private bot and move only after
  confirmed delivery.
- Candy is retired after the documented reconciliation and seven-day gate.

## Next goals

1. Complete seven successful daily radar runs and finish Candy decommissioning.
2. Add personal-assistant workflows incrementally behind policy gates.
3. Add n8n only when OAuth-heavy delivery creates measurable value.
4. Add Langfuse only after stable model workflows need evaluation/tracing.

See [docs/ecosystem.md](docs/ecosystem.md), [docs/architecture.md](docs/architecture.md),
[docs/cyber-radar.md](docs/cyber-radar.md) and
[docs/migration-from-candy.md](docs/migration-from-candy.md).
