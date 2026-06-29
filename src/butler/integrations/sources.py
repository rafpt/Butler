"""Authoritative and curated public cyber-intelligence sources."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urlencode, urljoin
from xml.etree import ElementTree

from butler.config import Settings
from butler.core.research import ResearchCategory, ResearchItem, SourceTier
from butler.integrations.http import BoundedHttpClient


class ResearchSource(Protocol):
    source_id: str

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]: ...


def _parse_datetime(value: object, *, default: datetime | None = None) -> datetime:
    if not value:
        return default or datetime.now(UTC)
    text = str(value).strip()
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return default or datetime.now(UTC)
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _clean_html(value: object, *, limit: int = 4000) -> str:
    text = re.sub(r"<[^>]{0,500}>", " ", str(value or ""))
    return " ".join(html.unescape(text).split())[:limit]


def _english_description(values: Iterable[dict[str, Any]]) -> str:
    for value in values:
        if value.get("lang") == "en" and value.get("value"):
            return str(value["value"])
    return ""


class CisaKevSource:
    source_id = "cisa-kev"
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self, client: BoundedHttpClient) -> None:
        self._client = client

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]:
        payload = self._client.get(self.url).json()
        result: list[ResearchItem] = []
        for record in payload.get("vulnerabilities", []):
            published = _parse_datetime(record.get("dateAdded"))
            if not start <= published <= end:
                continue
            cve = str(record.get("cveID", "")).upper()
            vendor = str(record.get("vendorProject", "")).strip()
            product = str(record.get("product", "")).strip()
            summary = " ".join(
                part
                for part in (
                    record.get("shortDescription", ""),
                    f"Ação exigida: {record.get('requiredAction', '')}",
                    f"Prazo CISA: {record.get('dueDate', '')}",
                )
                if part
            )
            tags = ["cisa-kev", vendor, product]
            if str(record.get("knownRansomwareCampaignUse", "")).casefold() == "known":
                tags.append("ransomware")
            result.append(
                ResearchItem(
                    source_id=self.source_id,
                    title=(
                        f"{cve}: {record.get('vulnerabilityName', 'Known exploited vulnerability')}"
                    ),
                    url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={cve}",
                    summary=summary,
                    published_at=published,
                    category=ResearchCategory.VULNERABILITY,
                    source_tier=SourceTier.AUTHORITATIVE,
                    authority=1.0,
                    severity=0.9,
                    exploited=True,
                    identifier=cve,
                    tags=tuple(filter(None, tags)),
                    content=json.dumps(record, ensure_ascii=False),
                )
            )
        return result


class NvdSource:
    source_id = "nvd"
    endpoint = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, client: BoundedHttpClient, *, api_key: str = "") -> None:
        self._client = client
        self._api_key = api_key

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]:
        query = urlencode(
            {
                "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "pubEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "resultsPerPage": 200,
            }
        )
        headers = {"apiKey": self._api_key} if self._api_key else {}
        payload = self._client.get(f"{self.endpoint}?{query}", headers=headers).json()
        result: list[ResearchItem] = []
        for wrapper in payload.get("vulnerabilities", []):
            cve = wrapper.get("cve", {})
            cve_id = str(cve.get("id", "")).upper()
            metrics = cve.get("metrics") or {}
            base_score = 0.0
            for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                if metrics.get(key):
                    base_score = float(metrics[key][0].get("cvssData", {}).get("baseScore", 0.0))
                    break
            weaknesses = [
                item.get("description", [{}])[0].get("value", "")
                for item in cve.get("weaknesses", [])
                if item.get("description")
            ]
            result.append(
                ResearchItem(
                    source_id=self.source_id,
                    title=f"{cve_id}: {_english_description(cve.get('descriptions', []))[:180]}",
                    url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    summary=_english_description(cve.get("descriptions", [])),
                    published_at=_parse_datetime(cve.get("published")),
                    category=ResearchCategory.VULNERABILITY,
                    source_tier=SourceTier.AUTHORITATIVE,
                    authority=0.95,
                    severity=min(1.0, round(base_score / 10, 2)),
                    identifier=cve_id,
                    tags=tuple(filter(None, ["nvd", *weaknesses])),
                    content=json.dumps(cve, ensure_ascii=False),
                )
            )
        return result


class GithubAdvisorySource:
    source_id = "github-advisories"
    endpoint = "https://api.github.com/advisories"

    def __init__(self, client: BoundedHttpClient, *, token: str = "") -> None:
        self._client = client
        self._token = token

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        payload = self._client.get(
            f"{self.endpoint}?per_page=100&sort=published&direction=desc", headers=headers
        ).json()
        severity_map = {"low": 0.25, "moderate": 0.5, "high": 0.75, "critical": 1.0}
        result: list[ResearchItem] = []
        for advisory in payload:
            published = _parse_datetime(advisory.get("published_at"))
            if not start <= published <= end:
                continue
            identifiers = advisory.get("identifiers") or []
            cve = next(
                (value.get("value", "") for value in identifiers if value.get("type") == "CVE"),
                "",
            )
            ghsa = str(advisory.get("ghsa_id", ""))
            vulnerabilities = advisory.get("vulnerabilities") or []
            ecosystems = [
                str(value.get("package", {}).get("ecosystem", ""))
                for value in vulnerabilities
                if value.get("package")
            ]
            result.append(
                ResearchItem(
                    source_id=self.source_id,
                    title=f"{cve or ghsa}: {advisory.get('summary', 'GitHub advisory')}",
                    url=str(advisory.get("html_url") or f"https://github.com/advisories/{ghsa}"),
                    summary=str(advisory.get("description") or advisory.get("summary") or ""),
                    published_at=published,
                    category=ResearchCategory.VULNERABILITY,
                    source_tier=SourceTier.AUTHORITATIVE,
                    authority=0.9,
                    severity=severity_map.get(str(advisory.get("severity", "")).casefold(), 0.4),
                    identifier=cve or ghsa,
                    tags=tuple(filter(None, ["github-advisory", *ecosystems])),
                    content=json.dumps(advisory, ensure_ascii=False),
                )
            )
        return result


class RssSource:
    def __init__(
        self,
        *,
        source_id: str,
        url: str,
        client: BoundedHttpClient,
        category: ResearchCategory,
        source_tier: SourceTier,
        authority: float,
        tags: Sequence[str] = (),
    ) -> None:
        self.source_id = source_id
        self.url = url
        self._client = client
        self.category = category
        self.source_tier = source_tier
        self.authority = authority
        self.tags = tuple(tags)

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]:
        root = ElementTree.fromstring(self._client.get(self.url).body)
        entries = root.findall(".//item")
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        result: list[ResearchItem] = []
        for entry in entries[:100]:
            title = _xml_value(entry, "title", "{http://www.w3.org/2005/Atom}title")
            link = _xml_value(entry, "link")
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                link = atom_link.attrib.get("href", "") if atom_link is not None else ""
            summary = _xml_value(
                entry,
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            )
            published = _parse_datetime(
                _xml_value(
                    entry,
                    "pubDate",
                    "published",
                    "updated",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                )
            )
            if not title or not link or not start <= published <= end:
                continue
            result.append(
                ResearchItem(
                    source_id=self.source_id,
                    title=title,
                    url=link,
                    summary=_clean_html(summary),
                    published_at=published,
                    category=self.category,
                    source_tier=self.source_tier,
                    authority=self.authority,
                    tags=(self.source_id, *self.tags),
                    content=_clean_html(summary, limit=20000),
                )
            )
        return result


def _xml_value(entry: ElementTree.Element, *names: str) -> str:
    for name in names:
        node = entry.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return ""


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(" ".join(self._text).split())))
            self._href = ""
            self._text = []


class HtmlIndexSource:
    def __init__(
        self,
        *,
        source_id: str,
        url: str,
        client: BoundedHttpClient,
        link_pattern: str,
        category: ResearchCategory,
        authority: float,
        tags: Sequence[str] = (),
        limit: int = 12,
        min_year: int | None = None,
    ) -> None:
        self.source_id = source_id
        self.url = url
        self._client = client
        self._link_pattern = re.compile(link_pattern, re.IGNORECASE)
        self.category = category
        self.authority = authority
        self.tags = tuple(tags)
        self.limit = limit
        self.min_year = min_year

    def fetch(self, start: datetime, end: datetime) -> list[ResearchItem]:
        parser = _LinkParser()
        parser.feed(self._client.get(self.url).text())
        seen: set[str] = set()
        result: list[ResearchItem] = []
        for href, title in parser.links:
            absolute = urljoin(self.url, href)
            if (
                not title
                or len(title) < 12
                or not self._link_pattern.search(f"{absolute} {title}")
                or absolute in seen
            ):
                continue
            years = [int(value) for value in re.findall(r"\b(20\d{2})\b", title)]
            if self.min_year is not None and years and max(years) < self.min_year:
                continue
            seen.add(absolute)
            result.append(
                ResearchItem(
                    source_id=self.source_id,
                    title=title,
                    url=absolute,
                    summary=f"Publicação identificada no índice oficial {self.source_id}.",
                    published_at=end,
                    category=self.category,
                    source_tier=SourceTier.AUTHORITATIVE,
                    authority=self.authority,
                    tags=(self.source_id, *self.tags),
                )
            )
            if len(result) >= self.limit:
                break
        return result


def default_sources(settings: Settings) -> list[ResearchSource]:
    """Create the v1 source set; each client is restricted to its source host."""

    def client(host: str) -> BoundedHttpClient:
        return BoundedHttpClient(
            allowed_hosts={host},
            timeout_seconds=settings.source_timeout_seconds,
            max_bytes=settings.source_max_bytes,
        )

    year = datetime.now(UTC).year
    return [
        CisaKevSource(client("www.cisa.gov")),
        NvdSource(client("services.nvd.nist.gov"), api_key=os_environ("NVD_API_KEY")),
        GithubAdvisorySource(client("api.github.com"), token=os_environ("GITHUB_TOKEN")),
        HtmlIndexSource(
            source_id="cert-eu",
            url=f"https://cert.europa.eu/publications/security-advisories/{year}",
            client=client("cert.europa.eu"),
            link_pattern=rf"/security-advisories/{year}-\d+",
            category=ResearchCategory.THREAT_INTEL,
            authority=0.95,
            tags=("eu", "advisory"),
        ),
        HtmlIndexSource(
            source_id="cncs",
            url="https://www.cncs.gov.pt/",
            client=client("www.cncs.gov.pt"),
            link_pattern=r"alert|vulnerab|nis\s?2|regime jurídico|cibersegurança",
            category=ResearchCategory.GOVERNANCE,
            authority=0.95,
            tags=("portugal", "cncs", "governance"),
            limit=8,
        ),
        HtmlIndexSource(
            source_id="enisa",
            url="https://www.enisa.europa.eu/press-office",
            client=client("www.enisa.europa.eu"),
            link_pattern=r"threat|security|cyber|nis2|certification|skills",
            category=ResearchCategory.GOVERNANCE,
            authority=0.95,
            tags=("eu", "enisa", "governance"),
            limit=8,
        ),
        HtmlIndexSource(
            source_id="apple-security",
            url="https://support.apple.com/en-us/100100",
            client=client("support.apple.com"),
            link_pattern=r"security|CVE-\d{4}-\d+",
            category=ResearchCategory.VULNERABILITY,
            authority=0.95,
            tags=("apple", "macos"),
            limit=8,
            min_year=year - 1,
        ),
        RssSource(
            source_id="docker-security-blog",
            url="https://www.docker.com/blog/category/security/feed/",
            client=client("www.docker.com"),
            category=ResearchCategory.VULNERABILITY,
            source_tier=SourceTier.AUTHORITATIVE,
            authority=0.85,
            tags=("docker",),
        ),
        RssSource(
            source_id="openai-news",
            url="https://openai.com/news/rss.xml",
            client=client("openai.com"),
            category=ResearchCategory.AI_SECURITY,
            source_tier=SourceTier.DISCOVERY,
            authority=0.75,
            tags=("ai", "openai"),
        ),
    ]


def os_environ(name: str) -> str:
    # Kept at the integration boundary so source construction is easy to test.
    import os

    return os.getenv(name, "")
