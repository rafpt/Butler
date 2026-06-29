import unittest
from datetime import UTC, datetime

from butler.core.research import (
    ResearchCategory,
    ResearchItem,
    SourceTier,
    canonicalize_url,
)


class ResearchDomainTests(unittest.TestCase):
    def test_canonicalize_url_removes_tracking(self) -> None:
        result = canonicalize_url(
            "HTTPS://Example.COM/path/?utm_source=newsletter&item=42#fragment"
        )
        self.assertEqual(result, "https://example.com/path?item=42")

    def test_canonicalize_url_rejects_local_and_relative_inputs(self) -> None:
        with self.assertRaises(ValueError):
            canonicalize_url("file:///etc/passwd")
        with self.assertRaises(ValueError):
            canonicalize_url("/relative")

    def test_item_id_is_stable(self) -> None:
        values = {
            "source_id": "test",
            "title": "Advisory",
            "url": "https://example.com/advisory",
            "summary": "Summary",
            "published_at": datetime(2026, 6, 29, tzinfo=UTC),
            "category": ResearchCategory.VULNERABILITY,
            "source_tier": SourceTier.AUTHORITATIVE,
            "authority": 0.9,
            "identifier": "CVE-2026-1234",
        }
        first = ResearchItem(**values)
        second = ResearchItem(**values)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.canonical_key, "cve-2026-1234")


if __name__ == "__main__":
    unittest.main()
