"""Deterministic ranking for Cyber Radar items."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from butler.core.research import (
    FeedbackAction,
    RadarSection,
    RankedItem,
    ResearchCategory,
    ResearchItem,
    WatchEntry,
)


def _freshness(item: ResearchItem, now: datetime) -> float:
    age_hours = max(0.0, (now - item.published_at.astimezone(UTC)).total_seconds() / 3600)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 72:
        return 0.7
    if age_hours <= 24 * 7:
        return 0.4
    return 0.1


def _watch_matches(item: ResearchItem, watches: list[WatchEntry]) -> tuple[tuple[str, ...], float]:
    searchable = " ".join(
        (item.title, item.summary, item.source_id, item.category.value, *item.tags)
    ).casefold()
    matched = tuple(
        entry.term
        for entry in watches
        if entry.active
        and re.search(
            rf"(?<![a-z0-9]){re.escape(entry.term)}(?![a-z0-9])",
            searchable,
        )
    )
    weights = [entry.weight for entry in watches if entry.term in matched]
    relevance = min(1.0, 0.2 + (max(weights, default=0.0) * 0.35))
    return matched, relevance


def score_item(
    item: ResearchItem,
    *,
    watches: list[WatchEntry],
    feedback: FeedbackAction | None,
    now: datetime,
) -> RankedItem:
    matches, relevance = _watch_matches(item, watches)
    freshness = _freshness(item, now)
    severity = max(item.severity, 0.85 if item.exploited else 0.0)
    score = relevance * 0.35 + severity * 0.30 + freshness * 0.20 + item.authority * 0.15
    rationale = [
        f"relevância={relevance:.2f}",
        f"severidade={severity:.2f}",
        f"frescura={freshness:.2f}",
        f"autoridade={item.authority:.2f}",
    ]
    if matches:
        rationale.append(f"watchlist={', '.join(matches)}")
    if item.exploited:
        score += 0.08
        rationale.append("exploração conhecida")
    if feedback is FeedbackAction.IGNORE:
        score = 0.0
        rationale.append("ignorado por feedback")
    elif feedback is FeedbackAction.SAVE:
        score += 0.05
        rationale.append("guardado anteriormente")
    elif feedback is FeedbackAction.FOLLOW:
        score += 0.10
        rationale.append("em acompanhamento")
    score = round(min(1.0, score), 4)

    if feedback is FeedbackAction.IGNORE:
        section = RadarSection.IGNORED
    elif score >= 0.78 or (item.exploited and severity >= 0.7):
        section = RadarSection.MUST
    elif item.category is ResearchCategory.GOVERNANCE:
        section = RadarSection.GOVERNANCE
    elif item.category in {ResearchCategory.LEARNING, ResearchCategory.AI_SECURITY}:
        section = RadarSection.LEARNING
    elif score >= 0.60:
        section = RadarSection.WORTH
    elif score >= 0.42:
        section = RadarSection.MONITOR
    else:
        section = RadarSection.IGNORED

    return RankedItem(
        item=item,
        score=score,
        section=section,
        rationale=tuple(rationale),
        watch_matches=matches,
    )


def rank_items(
    items: list[ResearchItem],
    *,
    watches: list[WatchEntry],
    feedback: dict[str, FeedbackAction],
    now: datetime,
    limit_per_section: int = 12,
) -> list[RankedItem]:
    ranked = [
        score_item(
            item,
            watches=watches,
            feedback=feedback.get(item.id),
            now=now,
        )
        for item in items
    ]
    ordered = sorted(
        ranked,
        key=lambda value: (
            value.section is RadarSection.IGNORED,
            -value.score,
            -value.item.published_at.timestamp(),
            value.item.id,
        ),
    )
    selected: list[RankedItem] = []
    for section in RadarSection:
        section_limit = 5 if section is RadarSection.IGNORED else limit_per_section
        selected.extend([value for value in ordered if value.section is section][:section_limit])
    return selected
