# Butler architecture

## Requirements and constraints

- One user, one Mac, local-first.
- Automation may propose actions; external or destructive actions need explicit policy decisions.
- SQLite is the default durable store until measured load proves otherwise.
- n8n schedules and transports events but does not own business rules or database access.
- LLM providers are replaceable adapters. Domain services must remain deterministic and testable
  without a model.

## Component boundaries

| Component | Owns | Must not own |
|---|---|---|
| `core` | Stable domain models and ports | Provider SDKs, HTTP, prompt files |
| `services` | Use cases and transaction orchestration | Transport-specific payloads |
| `memory` | Persistence implementations and migrations | Assistant behavior |
| `policies` | Autonomy, action risk, confirmation rules | Tool implementation |
| `tools` | Discoverable capability contracts | Workflow prompts |
| `skills` | Composable workflow definitions | Secrets or provider clients |
| `integrations` | n8n, macOS, model and service adapters | Domain decisions |
| `interfaces` | CLI, future API and UI | Direct database queries |

## Request flow

```text
user / n8n / macOS
        |
    interface adapter
        |
    application service ----> autonomy policy
        |                          |
        |                     allow / confirm / deny
        |
    domain port
        |
  SQLite / external adapter ----> append-only audit event
```

## Data model

The first schema keeps relational, queried state in one SQLite database:

- `tasks`: current task projection.
- `task_events`: append-only task history.
- `action_audit`: reserved central record for policy-gated actions.
- `research_items`: normalized cyber intelligence with stable provenance.
- `source_runs`: source-level health, counts, errors, and latency.
- `watch_entries`: relevance terms for technology, sector, regulation, and threats.
- `radar_reports` and `radar_report_items`: immutable daily report membership and ranking.
- `feedback_events`: explicit save, ignore, and follow dispositions.
- `schema_versions`: explicit migration checkpoint.

Human-editable configuration belongs in environment variables or versioned non-secret config.
Runtime memory should move into SQLite instead of being split across mutable JSON files.

## Reliability and observability

- WAL mode and per-operation transactions.
- Structured JSON logs.
- Append-only state transition events.
- Correlation IDs at automation boundaries.
- Future adapters should use bounded retries with jitter and idempotency keys.
- Scheduled research is isolated per source and publishes a degraded report on partial failure.
- Public-source content is treated as untrusted data and never controls tools.

## Trade-offs

- A modular monolith avoids deployment overhead while retaining clean boundaries.
- SQLite limits multi-host writes, which is acceptable for a single-Mac assistant.
- A central policy gate adds ceremony but makes proactive automation safe and auditable.
- The CLI and Codex skill are the initial interfaces; launchd schedules the daily radar.
- n8n remains outside the Butler v1 critical path.

## Revisit when

- Concurrent write contention is measured.
- The assistant becomes multi-user or multi-device.
- Semantic retrieval quality cannot be met by SQLite FTS plus metadata filters.
- An integration requires a continuously running HTTP service.
