"""Cyber research domain models."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4


class ResearchCategory(StrEnum):
    VULNERABILITY = "vulnerability"
    THREAT_INTEL = "threat_intel"
    GOVERNANCE = "governance"
    AI_SECURITY = "ai_security"
    LEARNING = "learning"
    NEWS = "news"


class SourceTier(StrEnum):
    AUTHORITATIVE = "authoritative"
    DISCOVERY = "discovery"


class RadarSection(StrEnum):
    MUST = "must"
    WORTH = "worth"
    MONITOR = "monitor"
    GOVERNANCE = "governance"
    LEARNING = "continuous_learning"
    IGNORED = "ignored_noise"


class FeedbackAction(StrEnum):
    SAVE = "save"
    IGNORE = "ignore"
    FOLLOW = "follow"


def canonicalize_url(value: str) -> str:
    """Normalize public citation URLs without changing their destination."""
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Research URLs must be absolute HTTP(S) URLs")
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
    ]
    hostname = parsed.hostname.lower()
    port = parsed.port
    netloc = hostname if port is None else f"{hostname}:{port}"
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(filtered_query), ""))


def research_item_id(source_id: str, identifier: str, url: str) -> str:
    stable = f"{source_id}|{identifier.casefold()}|{canonicalize_url(url)}"
    return f"item_{hashlib.sha256(stable.encode()).hexdigest()[:16]}"


@dataclass(frozen=True, slots=True)
class ResearchItem:
    source_id: str
    title: str
    url: str
    summary: str
    published_at: datetime
    category: ResearchCategory
    source_tier: SourceTier
    authority: float
    severity: float = 0.0
    exploited: bool = False
    identifier: str = ""
    tags: tuple[str, ...] = ()
    content: str = ""
    id: str = ""
    first_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_url = canonicalize_url(self.url)
        clean_title = " ".join(self.title.split())
        clean_summary = " ".join(self.summary.split())
        if not clean_title:
            raise ValueError("Research item title cannot be empty")
        if not 0.0 <= self.authority <= 1.0:
            raise ValueError("authority must be between 0 and 1")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be between 0 and 1")
        object.__setattr__(self, "url", normalized_url)
        object.__setattr__(self, "title", clean_title[:500])
        object.__setattr__(self, "summary", clean_summary[:4000])
        object.__setattr__(self, "content", self.content[:20000])
        object.__setattr__(self, "tags", tuple(dict.fromkeys(tag.casefold() for tag in self.tags)))
        if not self.id:
            object.__setattr__(
                self,
                "id",
                research_item_id(self.source_id, self.identifier or clean_title, normalized_url),
            )

    @property
    def canonical_key(self) -> str:
        if self.identifier:
            return self.identifier.casefold()
        return self.url

    @property
    def content_hash(self) -> str:
        value = f"{self.title.casefold()}|{self.summary.casefold()}"
        return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class WatchEntry:
    term: str
    kind: str
    weight: float = 1.0
    id: str = field(default_factory=lambda: f"watch_{uuid4().hex[:12]}")
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    item_id: str
    action: FeedbackAction
    note: str = ""
    id: str = field(default_factory=lambda: f"feedback_{uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class SourceRun:
    source_id: str
    status: str
    started_at: datetime
    completed_at: datetime
    received: int
    accepted: int
    error: str = ""
    id: str = field(default_factory=lambda: f"source_{uuid4().hex[:12]}")

    @property
    def duration_ms(self) -> int:
        return max(0, int((self.completed_at - self.started_at).total_seconds() * 1000))


@dataclass(frozen=True, slots=True)
class RankedItem:
    item: ResearchItem
    score: float
    section: RadarSection
    rationale: tuple[str, ...]
    watch_matches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RadarReport:
    report_date: date
    items: tuple[RankedItem, ...]
    source_runs: tuple[SourceRun, ...]
    synthesis: str
    degraded: bool
    model: str = ""
    id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", f"radar_{self.report_date:%Y%m%d}")

    @property
    def must_count(self) -> int:
        return sum(item.section is RadarSection.MUST for item in self.items)
