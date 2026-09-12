import httpx
from datetime import datetime
from typing import AsyncGenerator
from urllib.parse import quote_plus
from idea_hunter.collectors.base import BaseCollector, RawObservation
from idea_hunter.config import settings

class GitHubCollector(BaseCollector):
    """Collector for GitHub Issues (usually bug reports or feature requests)."""
    
    BASE_URL = "https://api.github.com/search/issues"
    
    def source_type(self) -> str:
        return "github"
        
    async def validate_credentials(self) -> bool:
        return bool(settings.github_token)
        
    async def collect(self, query: str, limit: int = 100) -> AsyncGenerator[RawObservation, None]:
        """Search GitHub Issues."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
            
        # Refine query to focus on issues
        refined_query = f"{query} type:issue"
        encoded_query = quote_plus(refined_query)
        
        async with httpx.AsyncClient() as client:
            hits_collected = 0
            page = 1
            
            while hits_collected < limit:
                url = f"{self.BASE_URL}?q={encoded_query}&per_page=50&page={page}"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 403:
                    print("GitHub API rate limit exceeded.")
                    break
                    
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break
                    
                for item in items:
                    if hits_collected >= limit:
                        break
                        
                    created_at_dt = None
                    try:
                        created_at_dt = datetime.fromisoformat(item.get("created_at").replace("Z", "+00:00"))
                    except:
                        pass
                        
                    yield RawObservation(
                        source_type=self.source_type(),
                        source_url=item.get("html_url"),
                        raw_text=f"{item.get('title')}\n{item.get('body', '')}",
                        author=item.get("user", {}).get("login"),
                        published_at=created_at_dt,
                        engagement=item.get("comments", 0) + item.get("reactions", {}).get("total_count", 0),
                        topic=query
                    )
                    hits_collected += 1
                page += 1
