"""Unit tests for the deterministic evidence spend gate."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from idea_hunter.application.services.gate import SpendGateResult, evaluate_spend_gate


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


def _obs(author: str, source_type: str | None = "reddit", published_ago_days: int = 5) -> object:
    return SimpleNamespace(
        author=author,
        source=SimpleNamespace(source_type=source_type),
        published_at=_days_ago(published_ago_days),
        collected_at=_days_ago(published_ago_days),
    )


def test_eligible_cluster_passes_gate():
    observations = [_obs("alice"), _obs("bob"), _obs("carol", "hackernews")]
    result = evaluate_spend_gate(observations)
    assert result.allowed is True
    assert result.reason == "eligible"
    assert result.independent_authors == 3
    assert result.source_count == 2


def test_too_few_independent_authors_is_blocked():
    # Only 2 distinct authors — below the default threshold of 3
    observations = [_obs("alice"), _obs("bob")]
    result = evaluate_spend_gate(observations)
    assert result.allowed is False
    assert result.reason == "needs_independent_authors"


def test_single_source_with_enough_authors_but_too_narrow_is_blocked():
    # 3 authors but all from same source and active window < min_active_days
    observations = [_obs("alice"), _obs("bob"), _obs("carol")]
    result = evaluate_spend_gate(observations)
    # All from 'reddit'; only 1 source. active_days = 0 (same day). Should block.
    assert result.allowed is False
    assert result.reason == "needs_source_or_time_diversity"


def test_single_source_with_wide_active_window_is_eligible():
    # 1 source but observations span 20+ days; active_days >= min_active_days (14)
    observations = [
        _obs("alice", "reddit", published_ago_days=20),
        _obs("bob", "reddit", published_ago_days=1),
        _obs("carol", "reddit", published_ago_days=10),
    ]
    result = evaluate_spend_gate(observations)
    assert result.allowed is True
    assert result.active_days >= 14


def test_stale_evidence_beyond_max_age_is_blocked():
    # All signals are 35+ days old; exceeds max_evidence_age_days default of 30
    observations = [
        _obs("alice", published_ago_days=35),
        _obs("bob", "hackernews", published_ago_days=36),
        _obs("carol", "devto", published_ago_days=37),
    ]
    result = evaluate_spend_gate(observations)
    assert result.allowed is False
    assert result.reason == "evidence_too_old"


def test_empty_observations_is_blocked():
    result = evaluate_spend_gate([])
    assert result.allowed is False
