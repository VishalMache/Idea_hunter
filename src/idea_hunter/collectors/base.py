import hashlib
from abc import ABC, abstractmethod
from typing import AsyncGenerator
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class RawObservation(BaseModel):
    """Schema for raw data collected from sources before processing."""
    source_type: str
    source_url: Optional[str] = None
    raw_text: str
    content_hash: str = Field(default="")
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    engagement: Optional[int] = 0
    topic: Optional[str] = None
    country: Optional[str] = None
    cursor_value: Optional[str] = None
    
    def model_post_init(self, __context):
        if not self.content_hash and self.raw_text:
            self.content_hash = hashlib.sha256(self.raw_text.encode('utf-8')).hexdigest()

class BaseCollector(ABC):
    """Abstract base class for all data collectors."""
    
    @abstractmethod
    def source_type(self) -> str:
        """Return the identifier for this source (e.g., 'reddit', 'hackernews')."""
        pass
        
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Check if API keys/auth are valid. Return True if no auth needed."""
        pass
        
    @abstractmethod
    async def collect(self, query: str, limit: int = 100, since_cursor: Optional[str] = None) -> AsyncGenerator[RawObservation, None]:
        """Collect data from the source matching the query."""
        pass
