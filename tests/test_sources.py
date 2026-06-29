import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from butler.core.research import ResearchCategory, SourceTier
from butler.integrations.http import BoundedHttpClient, HttpReadError, HttpResponse
from butler.integrations.sources import (
    CisaKevSource,
    GithubAdvisorySource,
    HtmlIndexSource,
    NvdSource,
    RssSource,
)

FIXTURES = Path(__file__).parent / "fixtures"
START = datetime(2026, 6, 28, tzinfo=UTC)
END = datetime(2026, 6, 30, tzinfo=UTC)


class FixtureClient:
    def __init__(self, fixture: str) -> None:
        self.fixture = FIXTURES / fixture

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> HttpResponse:
        del url, headers
        body = self.fixture.read_bytes()
        return HttpResponse(body=body, content_type="", status=200)


class SourceAdapterTests(unittest.TestCase):
    def test_cisa_fixture(self) -> None:
        result = CisaKevSource(FixtureClient("cisa_kev.json")).fetch(START, END)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].exploited)
        self.assertEqual(result[0].identifier, "CVE-2026-1234")

    def test_nvd_fixture(self) -> None:
        result = NvdSource(FixtureClient("nvd.json")).fetch(START, END)
        self.assertEqual(result[0].severity, 0.98)
        self.assertEqual(result[0].identifier, "CVE-2026-4321")

    def test_github_fixture(self) -> None:
        result = GithubAdvisorySource(FixtureClient("github_advisories.json")).fetch(START, END)
        self.assertEqual(result[0].severity, 1.0)
        self.assertIn("pip", result[0].tags)

    def test_rss_fixture(self) -> None:
        source = RssSource(
            source_id="docker",
            url="https://www.docker.com/feed",
            client=FixtureClient("feed.xml"),
            category=ResearchCategory.VULNERABILITY,
            source_tier=SourceTier.AUTHORITATIVE,
            authority=0.9,
        )
        result = source.fetch(START, END)
        self.assertEqual(len(result), 1)
        self.assertNotIn("utm_source", result[0].url)
        self.assertNotIn("<p>", result[0].summary)

    def test_html_index_fixture(self) -> None:
        source = HtmlIndexSource(
            source_id="cert-eu",
            url="https://cert.europa.eu/publications/security-advisories/2026",
            client=FixtureClient("index.html"),
            link_pattern=r"/security-advisories/2026-\d+",
            category=ResearchCategory.THREAT_INTEL,
            authority=0.95,
        )
        result = source.fetch(START, END)
        self.assertEqual(len(result), 1)
        self.assertIn("2026-009", result[0].url)

    def test_http_client_rejects_non_allowlisted_hosts(self) -> None:
        client = BoundedHttpClient(allowed_hosts={"example.com"})
        with self.assertRaises(HttpReadError):
            client.get("https://127.0.0.1/private")
        with self.assertRaises(HttpReadError):
            client.get("http://example.com/insecure")

    def test_fixture_json_is_valid(self) -> None:
        for fixture in ("cisa_kev.json", "nvd.json", "github_advisories.json"):
            json.loads((FIXTURES / fixture).read_text())


if __name__ == "__main__":
    unittest.main()
