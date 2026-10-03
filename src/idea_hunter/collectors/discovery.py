"""Compliant discovery adapters for sources with supported public interfaces."""
from datetime import datetime
from typing import AsyncGenerator, Any
from urllib.parse import quote_plus
import httpx
from idea_hunter.collectors.base import BaseCollector, RawObservation
from idea_hunter.config import settings

class DevToCollector(BaseCollector):
    BASE_URL = "https://dev.to/api/articles"
    def source_type(self) -> str: return "devto"
    async def validate_credentials(self) -> bool: return True
    @staticmethod
    def normalize_article(item: dict[str, Any], query: str) -> RawObservation | None:
        title = item.get("title")
        description = item.get("description") or item.get("body_markdown") or ""
        if not title and not description: return None
        published = None
        try: published = datetime.fromisoformat((item.get("published_at") or "").replace("Z", "+00:00"))
        except (TypeError, ValueError): pass
        tags = item.get("tag_list") or ""
        return RawObservation(source_type="devto", source_url=item.get("url") or item.get("canonical_url"), raw_text=f"{title or ''}\n{description}\nTags: {tags}".strip(), author=(item.get("user") or {}).get("username"), published_at=published, engagement=(item.get("positive_reactions_count") or 0)+(item.get("comments_count") or 0), topic=query, metadata={"title": title, "tags": tags, "cover_image": item.get("cover_image"), "signal_kind": "mixed"})
    async def collect(self, query: str, limit: int = 100, since_cursor: str | None = None) -> AsyncGenerator[RawObservation, None]:
        params = {"per_page": min(max(limit, 1), 100)}
        # DEV's public endpoint indexes tags; fall back to latest articles when the query is not a tag.
        if query and " " not in query: params["tag"] = query
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(self.BASE_URL, params=params, headers={"User-Agent": settings.collector_user_agent})
            response.raise_for_status()
            for item in response.json()[:limit]:
                normalized = self.normalize_article(item, query)
                if normalized: yield normalized

class ProductHuntCollector(BaseCollector):
    ENDPOINT = "https://api.producthunt.com/v2/api/graphql"
    def source_type(self) -> str: return "producthunt"
    async def validate_credentials(self) -> bool: return bool(settings.product_hunt_token)
    @staticmethod
    def normalize_post(post: dict[str, Any], query: str) -> RawObservation | None:
        name, tagline = post.get("name"), post.get("tagline") or post.get("description") or ""
        if not name and not tagline: return None
        made_on = None
        try: made_on = datetime.fromisoformat((post.get("createdAt") or "").replace("Z", "+00:00"))
        except (TypeError, ValueError): pass
        topics = ", ".join((edge.get("node") or {}).get("name", "") for edge in (post.get("topics") or {}).get("edges", []) if isinstance(edge, dict))
        return RawObservation(source_type="producthunt", source_url=post.get("url"), raw_text=f"{name or ''}\n{tagline}\nTopics: {topics}".strip(), author=((post.get("makers") or {}).get("edges") or [{}])[0].get("node", {}).get("username"), published_at=made_on, engagement=post.get("votesCount") or 0, topic=query, metadata={"title": name, "tagline": tagline, "topics": topics, "pricing": None, "signal_kind": "product_market_evidence"})
    async def collect(self, query: str, limit: int = 100, since_cursor: str | None = None) -> AsyncGenerator[RawObservation, None]:
        if not settings.product_hunt_token: raise RuntimeError("Product Hunt is disabled: PRODUCT_HUNT_TOKEN is not configured.")
        gql = '''query { posts(first: %d, order: NEWEST) { edges { node { name tagline url votesCount createdAt makers(first:1) { edges { node { username } } } topics(first:10) { edges { node { name } } } } } } }''' % min(max(limit, 1), 50)
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.ENDPOINT, json={"query": gql}, headers={"Authorization": f"Bearer {settings.product_hunt_token}", "Content-Type": "application/json", "User-Agent": settings.collector_user_agent})
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"): raise RuntimeError(f"Product Hunt API error: {payload['errors']}")
            for edge in payload.get("data", {}).get("posts", {}).get("edges", []):
                item = self.normalize_post(edge.get("node") or {}, query)
                if item: yield item

COLLECTOR_TYPES = {"devto": DevToCollector, "producthunt": ProductHuntCollector}
def get_collector(source_key: str) -> BaseCollector:
    try: return COLLECTOR_TYPES[source_key]()
    except KeyError as error: raise ValueError(f"No automated collector is enabled for '{source_key}'. Use a compliant manual import/export.") from error

