"""Unit tests for the evidence scorer source provenance fix.

The scorer must resolve source_type from the observation's ORM relationship,
not only from transient private attributes that are missing on persisted rows.
"""

from types import SimpleNamespace

from idea_hunter.analysis.scorer import EvidenceScorer


def _obs(source_type: str, author: str, engagement: int = 5) -> object:
    """Build a minimal observation with only the ORM relationship populated."""
    return SimpleNamespace(
        id=hash(author),
        author=author,
        engagement=engagement,
        raw_text="This is incredibly frustrating and tedious",
        published_at=None,
        collected_at=None,
        # Only the ORM relationship — no _source_type private attribute
        source=SimpleNamespace(source_type=source_type),
    )


def test_scorer_resolves_source_type_from_orm_relationship():
    """Source provenance must work even when _source_type private attr is absent."""
    obs = _obs("reddit", "alice", engagement=10)
    assert not hasattr(obs, "_source_type"), "fixture should not set _source_type"
    ledger = EvidenceScorer.calculate_ledger([obs], None, 0)
    # reddit has signal_kind='problem_evidence' in the source catalog
    assert ledger["problem_evidence_count"] >= 1 or ledger["user_complaints"] >= 1


def test_scorer_multi_source_diversity():
    """Observations from two different platform types count as platform diversity."""
    observations = [
        _obs("reddit", "user_a", engagement=8),
        _obs("hackernews", "user_b", engagement=15),
        _obs("reddit", "user_c", engagement=3),
    ]
    ledger = EvidenceScorer.calculate_ledger(observations, None, 0)
    assert ledger["platforms_covered"] == 2
    assert ledger["independent_sources"] == 3
    # Both sources are pain signals (reddit + hn both map to problem_evidence / mixed)
    assert ledger["user_complaints"] >= 2


def test_scorer_producthunt_does_not_inflate_complaint_count():
    """Product Hunt posts should NOT be counted as user complaints."""
    observations = [
        _obs("producthunt", "founder"),
        _obs("reddit", "real_user"),
    ]
    ledger = EvidenceScorer.calculate_ledger(observations, None, 0)
    assert ledger["product_market_evidence_count"] == 1
    # Only the reddit signal is a direct complaint
    assert ledger["problem_evidence_count"] == 1
    assert ledger["user_complaints"] == 1


def test_score_returns_recommendation_and_freshness():
    """Full score call must populate all required fields for the v1 API."""
    observations = [
        _obs("reddit", "a", engagement=5),
        _obs("hackernews", "b", engagement=12),
    ]
    problem = SimpleNamespace(
        severity=7,
        frequency=6,
    )
    result = EvidenceScorer.score(problem, None, observations, existing_solutions_count=2)
    assert "final_score" in result
    assert "potential_score" in result
    assert "confidence" in result
    assert "recommendation" in result
    assert "next_step" in result
    assert 0 <= result["final_score"] <= 1
    assert 0 <= result["potential_score"] <= 1
    assert 0 <= result["confidence"] <= 1
