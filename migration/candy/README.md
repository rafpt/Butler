# Candy workflow containment

The JSON files in `workflows/` are the exact published versions exported from n8n on
2026-06-29 before deactivation:

- Candy v3 — Feedback Loop
- Candy v3 — Source Ingest
- Candy v3 — Daily Digest

They contain credential references only, not secret values. Their n8n execution history was
preserved. They are migration evidence and must not be imported into Butler.
