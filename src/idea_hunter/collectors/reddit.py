import asyncpraw
from datetime import datetime
from typing import AsyncGenerator
from idea_hunter.collectors.base import BaseCollector, RawObservation
from idea_hunter.config import settings

class RedditCollector(BaseCollector):
    """Collector for Reddit using AsyncPRAW."""
    
    def __init__(self):
        self.reddit = None
        if settings.reddit_client_id and settings.reddit_client_secret:
            self.reddit = asyncpraw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent="IdeaHunter/0.1 by /u/ideahunter"
            )
            
    def source_type(self) -> str:
        return "reddit"
        
    async def validate_credentials(self) -> bool:
        if not self.reddit:
            return False
        try:
            # Simple test to verify connection
            user = await self.reddit.user.me()
            return True
        except Exception:
            return False
            
    async def collect(self, query: str, limit: int = 100) -> AsyncGenerator[RawObservation, None]:
        """Search Reddit across specified subreddits or globally."""
        if not self.reddit:
            print("Reddit credentials not set.")
            return
            
        # Parse query format: "query text | sub1,sub2"
        parts = query.split("|")
        search_query = parts[0].strip()
        subreddits = "all"
        if len(parts) > 1:
            subreddits = parts[1].strip().replace(" ", "")
            
        subreddit = await self.reddit.subreddit(subreddits)
        
        hits_collected = 0
        async for submission in subreddit.search(search_query, limit=limit):
            yield RawObservation(
                source_type=self.source_type(),
                source_url=f"https://reddit.com{submission.permalink}",
                raw_text=f"{submission.title}\n{submission.selftext}",
                author=submission.author.name if submission.author else "deleted",
                published_at=datetime.fromtimestamp(submission.created_utc),
                engagement=submission.score + submission.num_comments,
                topic=search_query
            )
            hits_collected += 1
            if hits_collected >= limit:
                break
                
        # In a real app we should close the connection gracefully
        # await self.reddit.close()
