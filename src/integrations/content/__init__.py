"""
Content integration layer.

Wraps NPS and future climbing content sources.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ContentProvider(ABC):
    """Abstract base for content providers (NPS, climbing guides, etc.)."""
    
    @abstractmethod
    def get_articles(self, location_id: str, limit: int = 50) -> List[Dict]:
        """Fetch articles/guides for a location."""
        pass


class NPSContentProvider(ContentProvider):
    """Wrapper around existing NPS article/content client."""
    
    def get_articles(self, location_id: str, limit: int = 50) -> List[Dict]:
        """
        Fetch articles from NPS.
        
        Args:
            location_id: NPS park code (e.g., "yose")
            limit: Max articles to fetch
        
        Returns:
            List of article dicts with metadata
        """
        from ...nps_articles import fetch_articles_for_park
        
        try:
            return fetch_articles_for_park(location_id, limit=limit)
        except Exception as e:
            print(f"[NPSContentProvider] Failed to fetch articles for {location_id}: {e}")
            return []
