"""Task domain model and persistence port."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4


class TaskStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    DONE = "done"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


OPEN_TASK_STATUSES = {
    TaskStatus.PENDING,
    TaskStatus.ACTIVE,
    TaskStatus.BLOCKED,
    TaskStatus.DEFERRED,
}


@dataclass(frozen=True, slots=True)
class Task:
    title: str
    id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 3
    notes: str = ""
    tags: tuple[str, ...] = ()
    due_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def with_status(self, status: TaskStatus) -> Task:
        return replace(self, status=status, updated_at=datetime.now(UTC))


class TaskRepository(Protocol):
    def add_task(self, task: Task, *, actor: str) -> None: ...

    def get_task(self, task_id: str) -> Task | None: ...

    def list_tasks(self, *, include_closed: bool = False) -> list[Task]: ...

    def save_task(self, task: Task, *, actor: str, reason: str) -> None: ...
