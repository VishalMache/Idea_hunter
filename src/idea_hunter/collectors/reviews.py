import asyncio
from typing import AsyncGenerator, Optional
from datetime import datetime
from google_play_scraper import search, reviews, Sort
from idea_hunter.collectors.base import BaseCollector, RawObservation

class PlayStoreReviewsCollector(BaseCollector):
    """Collector for Play Store app reviews (focuses on 1-3 star complaints)."""
    
    def source_type(self) -> str:
        return "playstore_reviews"
        
    async def validate_credentials(self) -> bool:
        return True # No auth required
        
    async def collect(self, query: str, limit: int = 100, since_cursor: Optional[str] = None) -> AsyncGenerator[RawObservation, None]:
        """Search for apps by category/keyword, then scrape their negative reviews."""
        
        # In a real app we might run this in a threadpool, but for now blocking search is okay
        # since it's just local CLI tooling
        try:
            app_results = search(query, lang="en", country="us", n_hits=5)
        except Exception as e:
            print(f"Error searching play store: {e}")
            return
            
        if not app_results:
            return
            
        hits_collected = 0
        
        for app in app_results:
            app_id = app['appId']
            app_title = app['title']
            
            # For each app, get recent negative/mediocre reviews (1-3 stars)
            for score_filter in [1, 2, 3]:
                if hits_collected >= limit:
                    return
                    
                try:
                    result, _ = reviews(
                        app_id,
                        lang='en',
                        country='us',
                        sort=Sort.NEWEST,
                        count=100,
                        filter_score_with=score_filter
                    )
                    
                    for review in result:
                        if hits_collected >= limit:
                            return
                            
                        content = review.get('content')
                        if not content:
                            continue
                            
                        # Contextualize the review so the LLM knows the domain
                        raw_text = f"Review for app '{app_title}' ({score_filter} stars): {content}"
                        review_id = review.get('reviewId')
                        
                        # We don't use since_cursor strictly here because we loop multiple apps.
                        # We rely heavily on PostgreSQL ON CONFLICT DO NOTHING (content_hash) for dedup.
                        
                        yield RawObservation(
                            source_type=self.source_type(),
                            source_url=f"https://play.google.com/store/apps/details?id={app_id}&reviewId={review_id}",
                            raw_text=raw_text,
                            author=review.get('userName'),
                            published_at=review.get('at'),
                            engagement=review.get('thumbsUpCount', 0),
                            topic=query,
                            cursor_value=review_id
                        )
                        hits_collected += 1
                except Exception as e:
                    print(f"Failed to scrape reviews for {app_id}: {e}")
                    continue
