import pytest
from idea_hunter.collectors.discovery import DevToCollector, ProductHuntCollector, get_collector
from idea_hunter.collectors.source_catalog import SOURCES, SOURCE_BY_KEY


def test_requested_source_catalog_is_complete_and_grouped():
    assert len(SOURCES) == 50
    assert {"Startup & Products", "Communities", "Customer Reviews", "SaaS & Software", "B2B", "AI"} <= {s.group for s in SOURCES}
    assert SOURCE_BY_KEY["reddit"].signal_kind == "problem_evidence"
    assert SOURCE_BY_KEY["producthunt"].signal_kind == "product_market_evidence"


def test_devto_normalization_preserves_provenance_and_metadata():
    observation = DevToCollector.normalize_article({"title": "API limits hurt", "description": "A painful workflow", "url": "https://dev.to/a", "published_at": "2026-01-01T10:00:00Z", "positive_reactions_count": 7, "comments_count": 3, "tag_list": ["saas"], "user": {"username": "maker"}}, "saas")
    assert observation.source_url == "https://dev.to/a"
    assert observation.author == "maker"
    assert observation.engagement == 10
    assert observation.metadata["title"] == "API limits hurt"
    assert observation.content_hash


def test_devto_skips_malformed_empty_article():
    assert DevToCollector.normalize_article({}, "saas") is None


def test_producthunt_normalization_is_product_market_not_pain():
    observation = ProductHuntCollector.normalize_post({"name": "ShipFast", "tagline": "Launch SaaS faster", "url": "https://producthunt.com/posts/shipfast", "votesCount": 42, "createdAt": "2026-01-01T10:00:00Z", "makers": {"edges": [{"node": {"username": "vismac"}}]}, "topics": {"edges": [{"node": {"name": "Developer Tools"}}]}}, "")
    assert observation.source_url.endswith("shipfast")
    assert observation.metadata["signal_kind"] == "product_market_evidence"
    assert "Developer Tools" in observation.metadata["topics"]


def test_unsupported_source_does_not_get_a_scraper():
    with pytest.raises(ValueError):
        get_collector("g2")
from idea_hunter.collectors.manual_import import iter_manual_observations


def test_manual_review_import_preserves_url_and_extra_fields(tmp_path):
    export = tmp_path / "reviews.json"
    export.write_text('[{"product":"Example CRM","review":"Missing bulk export","url":"https://example.test/review/1","rating":2,"buyer_type":"SMB"}]', encoding="utf-8")
    observation = next(iter_manual_observations("g2", export, "crm"))
    assert observation.source_url == "https://example.test/review/1"
    assert observation.metadata["imported"] is True
    assert observation.metadata["source_record"]["buyer_type"] == "SMB"
