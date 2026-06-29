# Butler

Butler is a local-first personal chief of staff for macOS. The active codebase is this
repository. `archive/Candy` is legacy migration input only and is intentionally excluded from
the package, runtime, and Git history.

## Current foundation

- Explicit autonomy policy with confirmation boundaries
- SQLite task repository with an append-only event trail
- Daily Cyber Radar with authoritative sources and deterministic ranking
- Local OMLX synthesis with manual-only cloud deep dives
- macOS and optional Telegram alerts through `@butleradelaidebot`
- CLI for health checks and task management
- JSON logs suitable for local collection and automation
- Small tool, skill, and integration contracts instead of agent-specific coupling

## Quick start

```bash
make test

PYTHONPATH=src python3 -m butler health
PYTHONPATH=src python3 -m butler task add "Prepare weekly review" --priority 2
PYTHONPATH=src python3 -m butler task list
PYTHONPATH=src python3 -m butler radar run --dry-run
```

Runtime data defaults to `~/Library/Application Support/Butler`. Override it for development:

```bash
BUTLER_DATA_DIR="$PWD/data" PYTHONPATH=src python3 -m butler health
```

## Cyber Radar

```bash
# Generate and persist today's report
PYTHONPATH=src python3 -m butler radar run

# Read the latest report and explain an item
PYTHONPATH=src python3 -m butler radar latest
PYTHONPATH=src python3 -m butler radar explain item_...

# Tune relevance and give feedback
PYTHONPATH=src python3 -m butler watch add "healthcare" --kind sector --weight 1.4
PYTHONPATH=src python3 -m butler feedback item_... follow

# Install the daily 07:30 launch agent
./scripts/install_launch_agent.sh

# Configure @butleradelaidebot securely in Keychain
./scripts/configure_telegram.sh
```

Reports are stored under
`~/Library/Application Support/Butler/reports/radar` unless `BUTLER_DATA_DIR` is overridden.
The scheduled job always uses OMLX and never reads cloud credentials.
Telegram delivery uses [`@butleradelaidebot`](https://t.me/butleradelaidebot) and is enabled
automatically when `bot-token` and `chat-id` exist under the `com.butler.telegram` service in
macOS Keychain. The BotFather token is never committed or written to the LaunchAgent plist.

## Architecture

```text
interfaces (CLI/API/automation)
           |
        services
     /      |       \
 policies  core   registries
           |
    memory adapters
           |
 integrations (n8n, macOS, providers)
```

See [docs/architecture.md](docs/architecture.md) and
[docs/migration-from-candy.md](docs/migration-from-candy.md). Cyber Radar runtime details are in
[docs/cyber-radar.md](docs/cyber-radar.md).
