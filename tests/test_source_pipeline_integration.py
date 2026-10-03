from idea_hunter.collectors.discovery import DevToCollector, ProductHuntCollector
from idea_hunter.processing.cleaner import TextCleaner
from idea_hunter.processing.deduplicator import Deduplicator
from idea_hunter.processing.prefilter import prefilter


def test_new_sources_share_the_existing_canonical_pipeline_contract():
    observations = [
        DevToCollector.normalize_article({"title": "Teams struggle with API limits", "description": "Retries are painful", "url": "https://dev.to/pain", "user": {"username": "dev"}}, "saas"),
        ProductHuntCollector.normalize_post({"name": "RetryBox", "tagline": "API retry tooling", "url": "https://producthunt.com/posts/retrybox"}, "saas"),
    ]
    deduplicator = Deduplicator()
    for observation in observations:
        cleaned = TextCleaner.process(observation.raw_text)
        assert cleaned
        assert observation.source_url
        assert isinstance(prefilter(cleaned, engagement=observation.engagement or 0).passed, bool)
        assert not deduplicator.is_duplicate(observation.source_url, cleaned)
    assert deduplicator.is_duplicate(observations[0].source_url, observations[0].raw_text)
