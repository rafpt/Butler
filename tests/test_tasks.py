import sqlite3
import tempfile
import unittest
from pathlib import Path

from butler.core.tasks import TaskStatus
from butler.memory import SqliteStore
from butler.policies.autonomy import AutonomyPolicy
from butler.services.tasks import DuplicateTaskError, PolicyDeniedError, TaskService


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "butler.db"
        self.store = SqliteStore(self.db_path)
        self.store.initialize()
        self.service = TaskService(self.store, AutonomyPolicy(2))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_and_complete_task_with_audit_events(self) -> None:
        task = self.service.create("  Prepare   weekly review ", priority=2, tags=("ops", "ops"))
        self.assertEqual(task.title, "Prepare weekly review")
        self.assertEqual(task.tags, ("ops",))

        completed = self.service.complete(task.id)
        self.assertEqual(completed.status, TaskStatus.DONE)
        self.assertEqual(self.service.list(), [])

        with sqlite3.connect(self.db_path) as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM task_events WHERE task_id = ?", (task.id,)
            ).fetchone()[0]
        self.assertEqual(event_count, 2)

    def test_duplicate_open_task_is_rejected(self) -> None:
        self.service.create("Review alerts")
        with self.assertRaises(DuplicateTaskError):
            self.service.create(" review   ALERTS ")

    def test_unapproved_automation_is_rejected(self) -> None:
        with self.assertRaises(PolicyDeniedError):
            self.service.create(
                "Automated suggestion",
                actor="automation",
                explicitly_approved=False,
            )


if __name__ == "__main__":
    unittest.main()
