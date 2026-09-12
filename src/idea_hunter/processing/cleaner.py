import re
from bs4 import BeautifulSoup

class TextCleaner:
    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
        
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Replace multiple spaces/newlines with a single space/newline."""
        if not text:
            return ""
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'[\r\n]+', '\n', text)
        return text.strip()
        
    @staticmethod
    def remove_urls(text: str) -> str:
        """Remove URLs from text as they often confuse LLMs and embedding models."""
        if not text:
            return ""
        url_pattern = re.compile(r'https?://\S+|www\.\S+')
        return url_pattern.sub('', text).strip()
        
    @staticmethod
    def process(text: str) -> str:
        """Full cleaning pipeline."""
        if not text:
            return ""
        text = TextCleaner.clean_html(text)
        text = TextCleaner.remove_urls(text)
        text = TextCleaner.normalize_whitespace(text)
        return text
