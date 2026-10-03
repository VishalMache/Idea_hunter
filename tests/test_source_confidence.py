from types import SimpleNamespace
from idea_hunter.analysis.scorer import EvidenceScorer
from idea_hunter.collectors.source_catalog import SOURCE_BY_KEY


def _obs(source_type, author, engagement=3):
    return SimpleNamespace(id=author, author=author, engagement=engagement, raw_text="This is frustrating", published_at=None, collected_at=None, source=SimpleNamespace(source_type=source_type))


def test_mixed_sources_raise_confidence_without_turning_launches_into_complaints():
    reddit = _obs("reddit", "a")
    product_hunt = _obs("producthunt", "b")
    ledger = EvidenceScorer.calculate_ledger([reddit, product_hunt], None, 0)
    assert ledger["user_complaints"] == 1
    assert ledger["problem_evidence_count"] == 1
    assert ledger["product_market_evidence_count"] == 1
    assert ledger["category_diversity"] >= 2
    assert 0 < ledger["source_quality_avg"] <= 1
