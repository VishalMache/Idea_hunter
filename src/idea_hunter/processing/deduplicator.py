import hashlib
import re

class Deduplicator:
    """Simple deduplicator using URL hashing and basic exact string matching."""
    
    def __init__(self):
        self.seen_urls = set()
        self.seen_text_hashes = set()
        
    def is_duplicate(self, url: str | None, text: str) -> bool:
        """Check if an item is a duplicate."""
        if url:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            if url_hash in self.seen_urls:
                return True
            self.seen_urls.add(url_hash)
            
        # Basic near-deduplication by normalizing and hashing text
        # (For Phase 1, MinHash/LSH is a bit heavy, simple hashing of normalized text works fine)
        normalized = re.sub(r'\W+', '', text.lower())
        if not normalized:
            return False
            
        text_hash = hashlib.md5(normalized.encode()).hexdigest()
        if text_hash in self.seen_text_hashes:
            return True
            
        self.seen_text_hashes.add(text_hash)
        return False
