import unittest
from datetime import UTC, datetime

from butler.core.research import (
    FeedbackAction,
    RadarSection,
    ResearchCategory,
    ResearchItem,
    SourceTier,
    WatchEntry,
)
from butler.research.scoring import rank_items, score_item


def item(
    *,
    category: ResearchCategory = ResearchCategory.VULNERABILITY,
    severity: float = 0.5,
    exploited: bool = False,
    title: str = "Docker security advisory",
) -> ResearchItem:
    return ResearchItem(
        source_id="test",
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        summary="Security update for Docker",
        published_at=datetime(2026, 6, 29, 6, tzinfo=UTC),
        category=category,
        source_tier=SourceTier.AUTHORITATIVE,
        authority=0.95,
        severity=severity,
        exploited=exploited,
    )


class ResearchScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 29, 7, 30, tzinfo=UTC)
        self.watches = [WatchEntry(term="docker", kind="technology", weight=1.5)]

    def test_exploited_relevant_item_is_must(self) -> None:
        ranked = score_item(
            item(severity=0.9, exploited=True),
            watches=self.watches,
            feedback=None,
            now=self.now,
        )
        self.assertEqual(ranked.section, RadarSection.MUST)
        self.assertIn("docker", ranked.watch_matches)

    def test_governance_item_gets_governance_section(self) -> None:
        ranked = score_item(
            item(
                category=ResearchCategory.GOVERNANCE,
                severity=0.1,
                title="NIS2 implementation guidance",
            ),
            watches=[],
            feedback=None,
            now=self.now,
        )
        self.assertEqual(ranked.section, RadarSection.GOVERNANCE)

    def test_ignore_feedback_forces_ignored_noise(self) -> None:
        ranked = score_item(
            item(severity=1.0, exploited=True),
            watches=self.watches,
            feedback=FeedbackAction.IGNORE,
            now=self.now,
        )
        self.assertEqual(ranked.score, 0.0)
        self.assertEqual(ranked.section, RadarSection.IGNORED)

    def test_ranking_is_deterministic(self) -> None:
        values = [item(title="A"), item(title="B", severity=0.9)]
        first = rank_items(values, watches=[], feedback={}, now=self.now)
        second = rank_items(list(reversed(values)), watches=[], feedback={}, now=self.now)
        self.assertEqual([value.item.id for value in first], [value.item.id for value in second])

    def test_watch_matching_uses_term_boundaries(self) -> None:
        ranked = score_item(
            item(title="nghttpx proxy request smuggling"),
            watches=[WatchEntry(term="httpx", kind="package", weight=2.0)],
            feedback=None,
            now=self.now,
        )
        self.assertNotIn("httpx", ranked.watch_matches)


if __name__ == "__main__":
    unittest.main()
