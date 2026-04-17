"""
Alert integration layer.

Provides abstract interface for fetching alerts from various sources.
"""

from abc import ABC, abstractmethod
from typing import List
from ...models import Alert


class AlertProvider(ABC):
    """Abstract base for alert providers (NPS, climbing orgs, etc.)."""
    
    @abstractmethod
    def get_alerts(self, location_id: str) -> List[Alert]:
        """Fetch alerts for a location."""
        pass


# Stub for future expansion
