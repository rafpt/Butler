# Candy to Butler migration

## Audit summary

Candy is a functional prototype: its legacy suite currently passes 98 tests. It should remain
read-only during extraction because it also contains local databases, runtime memory, an `.env`,
a 359 MB virtual environment, nested Git history, and uncommitted changes.

## Containment status — 2026-06-29

- Exported the published Feedback Loop, Source Ingest, and Daily Digest workflows to
  `migration/candy/workflows/`.
- Unpublished those three workflows in n8n and restarted the service to remove loaded triggers.
- Preserved all 50 Candy execution records.
- Verified the three active SecurityWork workflows remained published.
- Left Candy databases, `.env`, `.venv`, and source untouched pending the seven-day gate.

## Decisions

| Candy area | Decision | Reason |
|---|---|---|
| Task lifecycle and audit events | Reimplement incrementally | Useful behavior; legacy store and manager are tightly coupled |
| Source normalization, dedupe, ranking | Extract behind ports | Deterministic pipeline is reusable |
| SQLite + WAL | Keep | Correct local-first default |
| n8n over HTTP | Keep boundary | Scheduling stays peripheral |
| Autonomy levels and reversible actions | Redesign centrally | Candy documents policy but enforces it inconsistently |
| JSON runtime memory | Replace | Split sources of truth and weak transactional guarantees |
| `BaseAgent` inheritance | Drop | Couples prompt loading, result shape, and LLM access |
| Prompt-per-agent layering | Simplify | Prompts are loaded ad hoc with silent fallbacks |
| MLX/Anthropic router | Extract later | Provider construction and fallback are coupled to global settings |
| Multiple workflow generations | Drop after validation | `legacy`, `v1`, `v2`, and `v3` create operational ambiguity |
| Candy API route shapes | Compatibility only at ingress | Butler should not inherit internal legacy contracts |

## Observed technical debt

- Global cached settings and stores make dependency substitution harder.
- API authentication is route-local rather than middleware-enforced.
- Sync model calls are exposed through async handlers.
- Broad exception handlers can conceal persistence and provider failures.
- Mutable runtime state is spread across several SQLite databases and JSON files.
- Prompt loading differs between agents and briefing code, including silent fallback prompts.
- Model documentation and implementation disagree in places (Ollama/MLX/Anthropic).
- A deprecated FastAPI startup hook remains in use.
- Legacy `.env` and personal runtime data require explicit secure disposal.

## Incremental migration

1. **Foundation — complete**
   - Establish Butler package boundaries, policy gate, task vertical slice, audit trail, and tests.
2. **Task data**
   - Write a dry-run importer for Candy tasks.
   - Validate counts, statuses, timestamps, and event history.
   - Cut n8n task calls to Butler and keep Candy read-only for one review cycle.
3. **Signals and digests**
   - Port normalization, dedupe, ranking, and source adapters behind typed ports.
   - Consolidate databases and add idempotency keys.
   - Migrate one workflow end to end before the next.
4. **Memory and briefings**
   - Define memory provenance, confidence, retention, and supersession in SQLite.
   - Build briefing composition from structured sections; add LLM rendering last.
5. **Provider and macOS integrations**
   - Add model adapters, calendar/mail/notifications, and security-specific tools.
   - Every write-capable tool declares risk and reversibility.
6. **Retirement**
   - Export required data and encrypted secrets inventory.
   - Disable Candy launch agents, n8n workflows, and listeners.
   - Verify no calls for at least one review cycle.
   - Archive a sanitized source snapshot, then securely delete `.env`, databases, and `.venv`.

## Decommission gate

Candy may be retired only when:

- Migrated record counts and representative samples reconcile.
- Butler backups restore successfully.
- All active workflows point to Butler.
- No Candy process, launch agent, port, or scheduled workflow remains.
- Secret rotation is complete.
- A rollback snapshot exists and has a documented expiry date.

## Seven-day verification

After seven distinct daily Butler reports:

1. Confirm `launchctl print gui/$UID/com.butler.cyber-radar` shows seven successful runs.
2. Confirm n8n has no Candy executions newer than 2026-06-29.
3. Reconcile any Candy task/memory records explicitly selected for migration.
4. Export an encrypted rollback archive with an expiry date.
5. Rotate Candy-only credentials.
6. Remove Candy `.env`, runtime databases, `.venv`, launch agents, and then the sanitized source
   archive only after the rollback window expires.

Do not automate step 6; it is destructive and requires explicit user confirmation at the gate.
