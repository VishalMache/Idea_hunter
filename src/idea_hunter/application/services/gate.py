"""Deterministic hosted-model spend gate."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from idea_hunter.config import settings


@dataclass(frozen=True)
class SpendGateResult:
    allowed: bool
    reason: str
    independent_authors: int
    source_count: int
    active_days: int
    newest_age_days: int | None


def evaluate_spend_gate(observations: Iterable) -> SpendGateResult:
    items = list(observations)
    now = datetime.now(timezone.utc)
    authors = {item.author for item in items if getattr(item, "author", None)}
    sources = {
        getattr(getattr(item, "source", None), "source_type", None)
        or getattr(item, "source_id", None)
        for item in items
    }
    sources.discard(None)
    dates = []
    for item in items:
        value = getattr(item, "published_at", None) or getattr(item, "collected_at", None)
        if value:
            dates.append(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
    newest_age = min((max(0, (now - value).days) for value in dates), default=None)
    active_days = (max(dates) - min(dates)).days if len(dates) > 1 else 0

    if newest_age is None or newest_age > settings.spend_gate_max_evidence_age_days:
        return SpendGateResult(False, "evidence_too_old", len(authors), len(sources), active_days, newest_age)
    enough_authors = len(authors) >= settings.spend_gate_min_independent_authors
    enough_breadth = len(sources) >= settings.spend_gate_min_sources or active_days >= settings.spend_gate_min_active_days
    if not enough_authors:
        return SpendGateResult(False, "needs_independent_authors", len(authors), len(sources), active_days, newest_age)
    if not enough_breadth:
        return SpendGateResult(False, "needs_source_or_time_diversity", len(authors), len(sources), active_days, newest_age)
    return SpendGateResult(True, "eligible", len(authors), len(sources), active_days, newest_age)
