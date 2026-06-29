"""SQLite repository for cyber research state."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from butler.core.research import (
    FeedbackAction,
    FeedbackEvent,
    RadarReport,
    ResearchCategory,
    ResearchItem,
    SourceRun,
    SourceTier,
    WatchEntry,
)
from butler.memory.sqlite import SqliteStore


class ResearchRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def upsert_items(self, items: list[ResearchItem]) -> list[ResearchItem]:
        persisted: list[ResearchItem] = []
        with self._store._connection() as connection:
            for item in items:
                existing = connection.execute(
                    "SELECT id, first_seen_at FROM research_items WHERE canonical_key = ?",
                    (item.canonical_key,),
                ).fetchone()
                item_id = existing["id"] if existing else item.id
                first_seen = (
                    datetime.fromisoformat(existing["first_seen_at"])
                    if existing
                    else item.first_seen_at
                )
                stored = replace(item, id=item_id, first_seen_at=first_seen)
                connection.execute(
                    """
                    INSERT INTO research_items(
                        id, canonical_key, content_hash, source_id, title, url, summary, content,
                        published_at, category, source_tier, authority, severity, exploited,
                        identifier, tags, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_key) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        source_id = excluded.source_id,
                        title = excluded.title,
                        url = excluded.url,
                        summary = excluded.summary,
                        content = CASE
                            WHEN excluded.content != '' THEN excluded.content
                            ELSE research_items.content
                        END,
                        published_at = excluded.published_at,
                        category = excluded.category,
                        source_tier = excluded.source_tier,
                        authority = MAX(research_items.authority, excluded.authority),
                        severity = MAX(research_items.severity, excluded.severity),
                        exploited = MAX(research_items.exploited, excluded.exploited),
                        identifier = excluded.identifier,
                        tags = excluded.tags,
                        last_seen_at = excluded.last_seen_at
                    """,
                    self._item_values(stored),
                )
                persisted.append(stored)
        return persisted

    def get_item(self, item_id: str) -> ResearchItem | None:
        with self._store._connection() as connection:
            row = connection.execute(
                "SELECT * FROM research_items WHERE id = ?", (item_id,)
            ).fetchone()
        return self._row_to_item(row) if row else None

    def list_candidates(self, *, since: datetime, report_date: date) -> list[ResearchItem]:
        """Return recent items not included in an earlier day's report."""
        with self._store._connection() as connection:
            rows = connection.execute(
                """
                SELECT item.* FROM research_items item
                WHERE (item.published_at >= ? OR item.first_seen_at >= ?)
                  AND NOT EXISTS (
                    SELECT 1
                    FROM radar_report_items membership
                    JOIN radar_reports report ON report.id = membership.report_id
                    WHERE membership.item_id = item.id
                      AND report.report_date < ?
                  )
                ORDER BY item.published_at DESC, item.authority DESC
                """,
                (since.isoformat(), since.isoformat(), report_date.isoformat()),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def save_source_run(self, run: SourceRun) -> None:
        with self._store._connection() as connection:
            connection.execute(
                """
                INSERT INTO source_runs(
                    id, source_id, status, started_at, completed_at, duration_ms,
                    received, accepted, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.source_id,
                    run.status,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat(),
                    run.duration_ms,
                    run.received,
                    run.accepted,
                    run.error[:2000],
                ),
            )

    def add_watch(self, entry: WatchEntry) -> WatchEntry:
        if not entry.term.strip():
            raise ValueError("Watch term cannot be empty")
        if not 0.1 <= entry.weight <= 3.0:
            raise ValueError("Watch weight must be between 0.1 and 3.0")
        normalized = entry.term.strip().casefold()
        stored = replace(entry, term=normalized)
        try:
            with self._store._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO watch_entries(id, term, kind, weight, active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stored.id,
                        stored.term,
                        stored.kind,
                        stored.weight,
                        int(stored.active),
                        stored.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as error:
            message = f"Watch entry already exists: {stored.term} ({stored.kind})"
            raise ValueError(message) from error
        return stored

    def ensure_watches(self, entries: list[WatchEntry]) -> None:
        with self._store._connection() as connection:
            for entry in entries:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO watch_entries(
                        id, term, kind, weight, active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.term.strip().casefold(),
                        entry.kind,
                        entry.weight,
                        int(entry.active),
                        entry.created_at.isoformat(),
                    ),
                )

    def list_watches(self, *, active_only: bool = True) -> list[WatchEntry]:
        query = "SELECT * FROM watch_entries"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY kind, term"
        with self._store._connection() as connection:
            rows = connection.execute(query).fetchall()
        return [
            WatchEntry(
                id=row["id"],
                term=row["term"],
                kind=row["kind"],
                weight=float(row["weight"]),
                active=bool(row["active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def remove_watch(self, entry_id: str) -> bool:
        with self._store._connection() as connection:
            cursor = connection.execute(
                "UPDATE watch_entries SET active = 0 WHERE id = ? AND active = 1",
                (entry_id,),
            )
        return cursor.rowcount == 1

    def add_feedback(self, event: FeedbackEvent) -> None:
        if self.get_item(event.item_id) is None:
            raise LookupError(event.item_id)
        with self._store._connection() as connection:
            connection.execute(
                """
                INSERT INTO feedback_events(id, item_id, action, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.item_id,
                    event.action.value,
                    event.note[:1000],
                    event.created_at.isoformat(),
                ),
            )

    def latest_feedback(self, item_ids: list[str]) -> dict[str, FeedbackAction]:
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        with self._store._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT feedback.item_id, feedback.action
                FROM feedback_events feedback
                WHERE feedback.item_id IN ({placeholders})
                  AND feedback.created_at = (
                    SELECT MAX(latest.created_at)
                    FROM feedback_events latest
                    WHERE latest.item_id = feedback.item_id
                  )
                """,
                tuple(item_ids),
            ).fetchall()
        return {row["item_id"]: FeedbackAction(row["action"]) for row in rows}

    def save_report(self, report: RadarReport, *, path: Path) -> None:
        with self._store._connection() as connection:
            connection.execute(
                """
                INSERT INTO radar_reports(
                    id, report_date, path, synthesis, degraded, model, must_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    path = excluded.path,
                    synthesis = excluded.synthesis,
                    degraded = excluded.degraded,
                    model = excluded.model,
                    must_count = excluded.must_count,
                    created_at = excluded.created_at
                """,
                (
                    report.id,
                    report.report_date.isoformat(),
                    str(path),
                    report.synthesis,
                    int(report.degraded),
                    report.model,
                    report.must_count,
                    report.created_at.isoformat(),
                ),
            )
            connection.execute("DELETE FROM radar_report_items WHERE report_id = ?", (report.id,))
            for position, ranked in enumerate(report.items):
                connection.execute(
                    """
                    INSERT INTO radar_report_items(
                        report_id, item_id, score, section, rationale, watch_matches, position
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.id,
                        ranked.item.id,
                        ranked.score,
                        ranked.section.value,
                        json.dumps(ranked.rationale, ensure_ascii=False),
                        json.dumps(ranked.watch_matches, ensure_ascii=False),
                        position,
                    ),
                )

    def latest_report_path(self) -> Path | None:
        with self._store._connection() as connection:
            row = connection.execute(
                "SELECT path FROM radar_reports ORDER BY report_date DESC LIMIT 1"
            ).fetchone()
        return Path(row["path"]) if row else None

    def prune(self, *, now: datetime, content_days: int, report_days: int) -> None:
        content_cutoff = now - timedelta(days=content_days)
        report_cutoff = now.date() - timedelta(days=report_days)
        with self._store._connection() as connection:
            connection.execute(
                "UPDATE research_items SET content = '' WHERE last_seen_at < ?",
                (content_cutoff.isoformat(),),
            )
            connection.execute(
                "DELETE FROM radar_reports WHERE report_date < ?",
                (report_cutoff.isoformat(),),
            )

    def record_action(
        self,
        *,
        action: str,
        actor: str,
        decision: str,
        risk: str,
        reversible: bool,
        detail: str = "",
    ) -> None:
        self._store.record_action(
            action=action,
            actor=actor,
            decision=decision,
            risk=risk,
            reversible=reversible,
            detail=detail,
        )

    @staticmethod
    def _item_values(item: ResearchItem) -> tuple[object, ...]:
        return (
            item.id,
            item.canonical_key,
            item.content_hash,
            item.source_id,
            item.title,
            item.url,
            item.summary,
            item.content,
            item.published_at.isoformat(),
            item.category.value,
            item.source_tier.value,
            item.authority,
            item.severity,
            int(item.exploited),
            item.identifier,
            json.dumps(item.tags, ensure_ascii=False),
            item.first_seen_at.isoformat(),
            item.last_seen_at.isoformat(),
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ResearchItem:
        return ResearchItem(
            id=row["id"],
            source_id=row["source_id"],
            title=row["title"],
            url=row["url"],
            summary=row["summary"],
            content=row["content"],
            published_at=datetime.fromisoformat(row["published_at"]),
            category=ResearchCategory(row["category"]),
            source_tier=SourceTier(row["source_tier"]),
            authority=float(row["authority"]),
            severity=float(row["severity"]),
            exploited=bool(row["exploited"]),
            identifier=row["identifier"],
            tags=tuple(json.loads(row["tags"])),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        )
