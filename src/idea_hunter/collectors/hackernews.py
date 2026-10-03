import httpx
from datetime import datetime
from typing import AsyncGenerator, Optional
from urllib.parse import quote_plus
from idea_hunter.collectors.base import BaseCollector, RawObservation

class HackerNewsCollector(BaseCollector):
    """Collector for HackerNews using the free Algolia API."""
    
    BASE_URL = "https://hn.algolia.com/api/v1"
    
    def source_type(self) -> str:
        return "hackernews"
        
    async def validate_credentials(self) -> bool:
        return True # No auth required
        
    async def collect(self, query: str, limit: int = 100, since_cursor: Optional[str] = None) -> AsyncGenerator[RawObservation, None]:
        """Search HN comments (where the real problems are usually discussed)."""
        encoded_query = quote_plus(query)
        # Search primarily for comments containing the query
        url = f"{self.BASE_URL}/search_by_date?query={encoded_query}&tags=comment&hitsPerPage=50"
        
        async with httpx.AsyncClient() as client:
            hits_collected = 0
            page = 0
            
            while hits_collected < limit:
                response = await client.get(f"{url}&page={page}")
                response.raise_for_status()
                data = response.json()
                
                hits = data.get("hits", [])
                if not hits:
                    break # No more results
                    
                for hit in hits:
                    object_id = hit.get('objectID')
                    if since_cursor and str(object_id) == since_cursor:
                        return # We've reached the point where we left off last time!
                        
                    if hits_collected >= limit:
                        return
                        
                    # Some HN comments have no text if deleted
                    comment_text = hit.get("comment_text")
                    if not comment_text:
                        continue
                        
                    created_at_dt = None
                    try:
                        created_at_dt = datetime.fromisoformat(hit.get("created_at").replace("Z", "+00:00"))
                    except:
                        pass
                        
                    yield RawObservation(
                        source_type=self.source_type(),
                        source_url=f"https://news.ycombinator.com/item?id={object_id}",
                        raw_text=comment_text, # Contains HTML, cleaner will handle it
                        author=hit.get("author"),
                        published_at=created_at_dt,
                        engagement=hit.get("points", 0), # Comments usually don't have points in this API, but just in case
                        topic=query,
                        cursor_value=str(object_id)
                    )
                    hits_collected += 1
                page += 1
