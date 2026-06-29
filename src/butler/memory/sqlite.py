"""Single SQLite adapter for transactional state and audit events."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from butler.core.tasks import OPEN_TASK_STATUSES, Task, TaskStatus

_SCHEMA_VERSION = 2


class SqliteStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_versions (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 5),
                    notes TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    due_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
                    ON tasks(status, priority, created_at);
                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_events_task
                    ON task_events(task_id, created_at);
                CREATE TABLE IF NOT EXISTS action_audit (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    reversible INTEGER NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_items (
                    id TEXT PRIMARY KEY,
                    canonical_key TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_tier TEXT NOT NULL,
                    authority REAL NOT NULL,
                    severity REAL NOT NULL,
                    exploited INTEGER NOT NULL,
                    identifier TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_research_candidates
                    ON research_items(first_seen_at, published_at, category);
                CREATE INDEX IF NOT EXISTS idx_research_source
                    ON research_items(source_id, published_at);
                CREATE TABLE IF NOT EXISTS source_runs (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    received INTEGER NOT NULL,
                    accepted INTEGER NOT NULL,
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_source_runs_source_time
                    ON source_runs(source_id, started_at);
                CREATE TABLE IF NOT EXISTS watch_entries (
                    id TEXT PRIMARY KEY,
                    term TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    weight REAL NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(term, kind)
                );
                CREATE TABLE IF NOT EXISTS radar_reports (
                    id TEXT PRIMARY KEY,
                    report_date TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL,
                    synthesis TEXT NOT NULL,
                    degraded INTEGER NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    must_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS radar_report_items (
                    report_id TEXT NOT NULL REFERENCES radar_reports(id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL REFERENCES research_items(id),
                    score REAL NOT NULL,
                    section TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    watch_matches TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY(report_id, item_id)
                );
                CREATE INDEX IF NOT EXISTS idx_report_items_section
                    ON radar_report_items(report_id, section, position);
                CREATE TABLE IF NOT EXISTS feedback_events (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES research_items(id),
                    action TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_item_time
                    ON feedback_events(item_id, created_at);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (_SCHEMA_VERSION, datetime.now().astimezone().isoformat()),
            )

    def health(self) -> dict[str, object]:
        with self._connection() as connection:
            version = connection.execute("SELECT MAX(version) FROM schema_versions").fetchone()[0]
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": str(self.path), "schema_version": version}

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
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO action_audit(
                    id, action, actor, decision, risk, reversible, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"audit_{uuid4().hex[:12]}",
                    action,
                    actor,
                    decision,
                    risk,
                    int(reversible),
                    detail[:2000],
                    datetime.now().astimezone().isoformat(),
                ),
            )

    def add_task(self, task: Task, *, actor: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO tasks(
                    id, title, status, priority, notes, tags, due_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._task_values(task),
            )
            self._append_event(connection, task, "created", actor, "")

    def get_task(self, task_id: str) -> Task | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, *, include_closed: bool = False) -> list[Task]:
        query = "SELECT * FROM tasks"
        parameters: tuple[object, ...] = ()
        if not include_closed:
            placeholders = ",".join("?" for _ in OPEN_TASK_STATUSES)
            query += f" WHERE status IN ({placeholders})"
            parameters = tuple(status.value for status in OPEN_TASK_STATUSES)
        query += " ORDER BY priority ASC, created_at ASC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_task(row) for row in rows]

    def save_task(self, task: Task, *, actor: str, reason: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE tasks SET
                    title = ?, status = ?, priority = ?, notes = ?, tags = ?,
                    due_at = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    task.title,
                    task.status.value,
                    task.priority,
                    task.notes,
                    json.dumps(task.tags),
                    task.due_at.isoformat() if task.due_at else None,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(task.id)
            self._append_event(connection, task, "status_changed", actor, reason)

    @staticmethod
    def _task_values(task: Task) -> tuple[object, ...]:
        return (
            task.id,
            task.title,
            task.status.value,
            task.priority,
            task.notes,
            json.dumps(task.tags),
            task.due_at.isoformat() if task.due_at else None,
            task.created_at.isoformat(),
            task.updated_at.isoformat(),
        )

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            notes=row["notes"],
            tags=tuple(json.loads(row["tags"])),
            due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        task: Task,
        event_type: str,
        actor: str,
        reason: str,
    ) -> None:
        snapshot = {
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority,
        }
        connection.execute(
            """
            INSERT INTO task_events(
                id, task_id, event_type, actor, reason, snapshot, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"event_{uuid4().hex[:12]}",
                task.id,
                event_type,
                actor,
                reason,
                json.dumps(snapshot),
                datetime.now().astimezone().isoformat(),
            ),
        )
