"""Task use cases."""

from __future__ import annotations

import re

from butler.core.tasks import OPEN_TASK_STATUSES, Task, TaskRepository, TaskStatus
from butler.policies.autonomy import ActionRequest, AutonomyPolicy, Decision, Risk


class DuplicateTaskError(ValueError):
    pass


class TaskNotFoundError(LookupError):
    pass


class PolicyDeniedError(PermissionError):
    pass


def _normalized_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip()).casefold()


class TaskService:
    def __init__(self, repository: TaskRepository, policy: AutonomyPolicy) -> None:
        self._repository = repository
        self._policy = policy

    def create(
        self,
        title: str,
        *,
        priority: int = 3,
        notes: str = "",
        tags: tuple[str, ...] = (),
        actor: str = "user",
        explicitly_approved: bool = True,
    ) -> Task:
        clean_title = " ".join(title.split())
        if not clean_title:
            raise ValueError("Task title cannot be empty")
        if len(clean_title) > 300:
            raise ValueError("Task title cannot exceed 300 characters")
        if priority not in range(1, 6):
            raise ValueError("Priority must be between 1 and 5")

        result = self._policy.evaluate(
            ActionRequest(
                action="task.create",
                risk=Risk.LOW,
                reversible=True,
                initiated_by=actor,
                explicitly_approved=explicitly_approved,
            )
        )
        if result.decision is not Decision.ALLOW:
            raise PolicyDeniedError(result.reason)

        normalized = _normalized_title(clean_title)
        for existing in self._repository.list_tasks(include_closed=False):
            is_duplicate = (
                existing.status in OPEN_TASK_STATUSES
                and _normalized_title(existing.title) == normalized
            )
            if is_duplicate:
                raise DuplicateTaskError(f"Open task already exists: {existing.id}")

        task = Task(
            title=clean_title,
            priority=priority,
            notes=notes.strip(),
            tags=tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip())),
        )
        self._repository.add_task(task, actor=actor)
        return task

    def complete(self, task_id: str, *, actor: str = "user") -> Task:
        task = self._repository.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if task.status is TaskStatus.DONE:
            return task
        updated = task.with_status(TaskStatus.DONE)
        self._repository.save_task(updated, actor=actor, reason="completed")
        return updated

    def list(self, *, include_closed: bool = False) -> list[Task]:
        return self._repository.list_tasks(include_closed=include_closed)
