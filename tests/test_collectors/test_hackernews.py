import pytest
from idea_hunter.collectors.hackernews import HackerNewsCollector

@pytest.mark.asyncio
async def test_hn_collector_fetches_data():
    collector = HackerNewsCollector()
    assert await collector.validate_credentials() is True
    assert collector.source_type() == "hackernews"
    
    # Collect a small amount of data
    observations = []
    async for obs in collector.collect(query="frustrated with", limit=2):
        observations.append(obs)
        
    assert len(observations) == 2
    for obs in observations:
        assert obs.source_type == "hackernews"
        assert obs.raw_text is not None
        assert "frustrated with" in obs.topic
