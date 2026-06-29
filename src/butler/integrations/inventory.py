"""Read-only extraction of relevant technology terms from local manifests."""

from __future__ import annotations

import re
from pathlib import Path

from butler.core.research import WatchEntry

DEFAULT_WATCHES = (
    ("macos", "technology", 1.4),
    ("apple", "vendor", 1.1),
    ("microsoft", "vendor", 1.3),
    ("microsoft 365", "technology", 1.4),
    ("python", "technology", 1.1),
    ("docker", "technology", 1.4),
    ("kubernetes", "technology", 1.2),
    ("n8n", "technology", 1.4),
    ("langfuse", "technology", 1.2),
    ("openai", "vendor", 1.1),
    ("nis2", "regulation", 1.5),
    ("dora", "regulation", 1.4),
    ("ai act", "regulation", 1.3),
    ("ransomware", "threat", 1.3),
    ("supply chain", "threat", 1.2),
)


def default_watch_entries() -> list[WatchEntry]:
    return [
        WatchEntry(term=term, kind=kind, weight=weight) for term, kind, weight in DEFAULT_WATCHES
    ]


def securitywork_inventory_terms(root: Path, *, limit: int = 80) -> set[str]:
    """Read package names only; never execute or modify SecurityWork."""
    candidates = [
        root / "ai_development" / "requirements.txt",
        root / "pyproject.toml",
    ]
    terms: set[str] = set()
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean = line.split("#", 1)[0].strip()
            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]{2,})", clean)
            if match:
                terms.add(match.group(1).replace("_", "-").casefold())
            if len(terms) >= limit:
                return terms
    return terms
