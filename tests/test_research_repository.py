import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from butler.core.research import (
    FeedbackAction,
    FeedbackEvent,
    RadarReport,
    RadarSection,
    RankedItem,
    ResearchCategory,
    ResearchItem,
    SourceTier,
    WatchEntry,
)
from butler.memory import ResearchRepository, SqliteStore


def make_item() -> ResearchItem:
    return ResearchItem(
        source_id="test",
        title="Critical Docker advisory",
        url="https://example.com/advisory",
        summary="Update immediately",
        published_at=datetime(2026, 6, 29, tzinfo=UTC),
        category=ResearchCategory.VULNERABILITY,
        source_tier=SourceTier.AUTHORITATIVE,
        authority=0.9,
        severity=0.9,
        identifier="CVE-2026-9999",
        tags=("docker",),
    )


class ResearchRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteStore(Path(self.temp_dir.name) / "butler.db")
        self.store.initialize()
        self.repository = ResearchRepository(self.store)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_upsert_feedback_and_report(self) -> None:
        stored = self.repository.upsert_items([make_item()])[0]
        duplicate = make_item()
        second = self.repository.upsert_items([duplicate])[0]
        self.assertEqual(stored.id, second.id)

        self.repository.add_feedback(FeedbackEvent(item_id=stored.id, action=FeedbackAction.FOLLOW))
        self.assertEqual(
            self.repository.latest_feedback([stored.id])[stored.id],
            FeedbackAction.FOLLOW,
        )

        ranked = RankedItem(
            item=stored,
            score=0.9,
            section=RadarSection.MUST,
            rationale=("critical",),
        )
        report = RadarReport(
            report_date=date(2026, 6, 29),
            items=(ranked,),
            source_runs=(),
            synthesis="Resumo",
            degraded=False,
        )
        path = Path(self.temp_dir.name) / "report.md"
        path.write_text("report")
        self.repository.save_report(report, path=path)
        self.assertEqual(self.repository.latest_report_path(), path)

    def test_watch_lifecycle(self) -> None:
        entry = self.repository.add_watch(WatchEntry(term="Healthcare", kind="sector", weight=1.4))
        self.assertEqual(self.repository.list_watches()[0].term, "healthcare")
        self.assertTrue(self.repository.remove_watch(entry.id))
        self.assertEqual(self.repository.list_watches(), [])


if __name__ == "__main__":
    unittest.main()
